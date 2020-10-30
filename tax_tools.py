import json
import urllib.request
import urllib.error
import time
import argparse
import calendar
import datetime
import csv
import os.path
from os import path
from utils import load_hotspots, api_call
from dateutil.parser import parse
from dateutil import tz
from datetime import timedelta
from classes.Hotspots import Hotspots
from datetime import datetime
from math import radians, cos, sin, asin, sqrt, log10, ceil, degrees, atan2

g_hnt_adjust = 100000000 #divisor for hnt value rep
g_include_transaction_fees = False #experimental, toggle on to try to include txn fees/assert location fees

def load_hnt_rewards(hotspot, use_realtime_oracle_price=True, num_rewards=10000):
   for hotspot in hotspots:
      rewards = load_api_hotspot_rewards(hotspot,use_realtime_oracle_price,num_rewards)
      print("Got: {len(rewards)} rewards")
      f = open(f"data/{hotspot['name']}.csv", "w")
      for reward in reversed(rewards):
         as_of_time = reward['timestamp']
         amount = reward['amount']
         block = reward['block']
         oracle_price = 0
         #oracle_price = load_oracle_price_at_block(block)['price']
         print(f"{as_of_time},{amount},{oracle_price},{block}")
         f.write(f"{as_of_time},{amount},{oracle_price},{block}\n")
      f.close()

def load_api_hotspot_rewards(hotspot, use_realtime_oracle_price=True, num_rewards=10000):  
   address = hotspot['address']
   time_range = get_hotspot_min_max_time(hotspot)
   min_time = time_range[0]
   max_time = time_range[1]      
   rewards = load_api_hotspot_rewards_impl(address, min_time, max_time, num_rewards)
   return rewards

def load_api_hotspot_rewards_impl(address, min_time, max_time, num_rewards):
   cursor = None
   rewards = []
   while len(rewards) < num_rewards:
      path = f"hotspots/{address}/rewards?max_time={max_time}&min_time={min_time}"
      #print(path)
      if cursor:
         path += f"&cursor={cursor}"
      result = api_call(path=path)
      #print(f"-I- loaded {len(result['data'])} rewards")
      cursor = result.get('cursor')

      rewards.extend(result['data'])
      if not cursor:
         break
      #print(rewards)
   return rewards 

def load_api_account_transactions(account, num_transactions):
   api_transactions = load_api_account_transactions_impl(account, num_transactions)
   transactions = get_transactions(account, api_transactions)
   return transactions
   
def load_api_account_transactions_impl(account, num_transactions):
   cursor = None
   transactions = []
   while len(transactions) < num_transactions:
      path = f"accounts/{account}/pending_transactions"
      #print(path)
      if cursor:
         path += f"?cursor={cursor}"
      result = api_call(path=path)
      #print(f"-I- loaded {len(result['data'])} transactions") 
      cursor = result.get('cursor')
      print(cursor)

      transactions.extend(result['data'])
      if not cursor:
         break
         
   return transactions
   
def get_hotspot_min_max_time(hotspot, include_current_year_only=True):
   first_block = hotspot['block_added']
   max_date = datetime.now() + timedelta(days=1) #mostly for UTC nonsense
   max_time = max_date.date().isoformat()
   min_date = get_block_date_time(first_block).date()
   min_date = min_date - timedelta(days=1) #mostly for UTC nonsense
   min_time = min_date.isoformat()
   return (min_time, max_time)
   
def load_tax_lots(hotspots):
   tax_lots = []
   prices_by_date = get_hnt_open_prices()
   transactions_by_account = {}
   
   #get modified transactions which are basically just fees from payments/assertions to fix cost basis when possible
   if g_include_transaction_fees:
      for hotspot in hotspots:   
         account = hotspot['owner']
         if account not in transactions_by_account.keys():
            transactions = load_api_account_transactions(account, 10000)
            modified_transactions = get_modified_transactions(account, transactions) # only looks at fees really
            transactions_by_account[account] = modified_transactions         
      print(transactions_by_account)
     
   for hotspot in hotspots:
      filename = f"data/{hotspot['name']}.csv"
      file_exists = path.exists(filename)
      if file_exists != True:
         load_hnt_rewards(hotspot)

      hotspot_account = hotspot['owner']
      account_transactions = []
      if hotspot_account in transactions_by_account.keys():
         account_transactions = transactions_by_account[hotspot_account]
         del transactions_by_account[hotspot_account] #don't double count if same owner owns multiple
      hotspot_day_lots = consolidate_day_lots(filename)
      hotspot_tax_lots = output_tax_lots_by_day(hotspot, hotspot_day_lots, account_transactions, prices_by_date)
      tax_lots.extend(hotspot_tax_lots)
   return tax_lots

def output_tax_lots_by_day(hotspot, day_lots, account_transactions, prices_by_date):
    tax_lots = []    
    total_hnt = 0
    total_usd = 0
    hotspot_name = hotspot['name']
    filename = f"output/{hotspot_name}_tax_lots.csv"    
       
    #back out any fees from payments or assertions (for now)   
    usd_fees_by_date = {}
    for account_transaction in account_transactions:
       transaction_date = account_transaction['update_time']
       usd_amount = account_transaction['usd_amount']    
       if transaction_date in usd_fees_by_date.keys():
          usd_fees_by_date[transaction_date] += usd_amount
       else:
          usd_fees_by_date[transaction_date] = usd_amount
    
    for key in day_lots:
        date = key
        hnt_fees = 0
        
        hnt_price = 0
        if date in prices_by_date:
           hnt_price = prices_by_date[date]
        
        if date in usd_fees_by_date:
           usd_fees = usd_fees_by_date[date]
           hnt_fees = usd_fees / hnt_price #intentional divide by zero to warn we don't have a valid price
           print(f'fees: {date} hnt: {hnt_fees} usd:{usd_fees}')
        
        hnt_amount = day_lots[key]
        hnt_amount_adj = hnt_amount / g_hnt_adjust
        hnt_amount_adj += hnt_fees
        usd_amount = hnt_amount_adj * hnt_price
        total_hnt += hnt_amount_adj
        total_usd += usd_amount
        tax_lot = {}
        tax_lot['time'] = date
        tax_lot['hotspot'] = hotspot_name
        tax_lot['hnt_amount'] = hnt_amount_adj
        tax_lot['hnt_price'] = hnt_price
        tax_lot['usd_amount'] = usd_amount
        tax_lots.append(tax_lot)
    output_tax_lots(tax_lots, filename)

    print(f'Total HNT: {total_hnt}, Total USD: {total_usd}')
    return tax_lots

def output_tax_lots(tax_lots, filename):
   f = open(f"{filename}", "w")
   msg = f'date,hotspot,hnt_amount,hnt_price,usd_amount'
   print(f'{msg}')
   f.write(f'{msg}\n')
   for tax_lot in tax_lots:
      date = tax_lot['time']
      hotspot_name = tax_lot['hotspot']
      hnt_amount_adj = tax_lot['hnt_amount']
      hnt_price = tax_lot['hnt_price']
      usd_amount = tax_lot['usd_amount']
      msg = f'{date},{hotspot_name},{hnt_amount_adj},{hnt_price},{usd_amount}'
      print(f'{msg}')
      f.write(f'{msg}\n')

def get_hnt_open_prices(filename ='data/hnt-prices.csv'):
    print(f'reading prices from {filename}')
    prices_by_date = {}
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0;
        for row in csv_reader:
            line_count += 1
            if (line_count == 1):
                continue
            time_stamp_str = row[0]
            time_stamp = parse(time_stamp_str)
            date_stamp = time_stamp.date()
            price_str = row[1]
            price = float(price_str)
            prices_by_date[date_stamp] = price
    return prices_by_date

#takes all transactions and consolidates them into a single tax lot per day
def consolidate_day_lots(filename):
    print(f'reading from {filename}')
    amounts_by_date = {}
    total = 0 
    
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            time_stamp_str = row[0]
            time_stamp = parse(time_stamp_str)
            time_stamp_adj = utc_to_local(time_stamp)
            #print(time_stamp)
            #print(time_stamp_adj)
            date_stamp = time_stamp_adj.date() #handle timezone?
            amount = int(row[1])
            block = row[2]
            #print(f'{time_stamp}, {date_stamp}: {amount}')

            if date_stamp in amounts_by_date.keys():
                amounts_by_date[date_stamp] += amount
            else:
                amounts_by_date[date_stamp] = amount
            total += amount

    #print(amounts_by_date)
    #print(f'Total: {total}')
    return amounts_by_date

def parse_trades(filename):
    #binance for now
    print(f'reading trades from {filename}')
    trades = []
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0;
        for row in csv_reader:
            line_count += 1
            if (line_count == 1):
                continue
            time_stamp_str = row[0]
            time_stamp = parse(time_stamp_str)
            time_stamp_adj = utc_to_local(time_stamp)
            hnt_price = float(row[3])
            hnt_amount = float(row[4])
            trade = {}
            trade['time'] = time_stamp_adj
            trade['hnt_price'] = hnt_price
            trade['hnt_amount'] = hnt_amount
            trade['exchange'] = 'binance' #support others later
            trades.append(trade)
#    print(trades)
    return trades

def process_trades(hotspots, filename):
   trades = parse_trades(filename)
   tax_lots = load_tax_lots(hotspots)
   result =  get_schedule_d(tax_lots, trades)
   schedule_d_items = result[0]
   remaining_tax_lots = result[1]
   output_schedule_d(schedule_d_items)
   filename = 'output/remaining_tax_lots.csv'
   output_tax_lots(remaining_tax_lots, filename)

def get_schedule_d(tax_lots, trades):
   schedule_d_items = []
   total_gain_loss = 0
   sorted_tax_lots = sorted(tax_lots, key=lambda x: (x['time'], x['hotspot']))
   remaining_tax_lots = []
   for trade in reversed(trades): #order by time
      trade_time = trade['time']
      trade_hnt_price = trade['hnt_price']
      remaining_amount = trade['hnt_amount']
      for tax_lot in sorted_tax_lots: #order by time (FIFO only now)
         tax_lot_amount = tax_lot['hnt_amount']
         if tax_lot_amount  == 0:
            continue
         tax_lot_hnt_price = tax_lot['hnt_price']
         schedule_d_amount = 0
         schedule_d_time = trade_time
         schedule_d_gain_loss = 0
         if tax_lot_amount > remaining_amount:
            schedule_d_amount = remaining_amount
            tax_lot_amount -= remaining_amount
            remaining_amount = 0
         else:
            schedule_d_amount = tax_lot_amount
            remaining_amount -= tax_lot_amount
            tax_lot_amount = 0
         if schedule_d_amount == 0:
            continue
         tax_lot['hnt_amount'] = tax_lot_amount
         schedule_d_gain_loss = schedule_d_amount * (trade_hnt_price - tax_lot_hnt_price)
         schedule_d_item = {}
         schedule_d_item['open_time'] = tax_lot['time']
         schedule_d_item['close_time'] = schedule_d_time
         schedule_d_item['open_price'] = tax_lot_hnt_price
         schedule_d_item['close_price'] = trade_hnt_price
         schedule_d_item['gain_loss'] = schedule_d_gain_loss
         schedule_d_items.append(schedule_d_item)
         total_gain_loss += schedule_d_gain_loss
         print(schedule_d_item)
   for tax_lot in sorted_tax_lots:
      if tax_lot['hnt_amount'] != 0:
         remaining_tax_lots.append(tax_lot)
         print(tax_lot)
   print(total_gain_loss)
   #print(schedule_d_items)
   return schedule_d_items, remaining_tax_lots

def output_schedule_d(items):
    f = open(f"output/schedule_d.csv", "w")
    msg = f'open_time,close_time,open_price,close_price,gain_loss,gain,loss,longshort'
    print(f'{msg}')
    f.write(f'{msg}\n')
    for item in items:
       open_time = item['open_time']
       close_time = item['close_time']
       open_price = item['open_price']
       close_price = item['close_price']
       gain_loss = item['gain_loss']
       gain = 0
       loss = 0
       if gain_loss >= 0:
           gain = gain_loss
       else:
           loss = gain_loss
       longshort = 'short' #default short
       diff_days = (close_time.date() - open_time).days
       if diff_days >= 365:
           longshort = 'long'
       msg = f'{open_time},{close_time},{open_price},{close_price},{gain_loss},{gain},{loss},{longshort}'
       print(f'{msg}')
       f.write(f'{msg}\n')

def get_block_date_time(block):
    path = f"blocks/{block}"
    result = api_call(path=path)
    print(result)
    time = result["data"]["time"]
    as_of_time = datetime.fromtimestamp(time)
    print(as_of_time)
    return as_of_time
    
#pulls/parses relevant transactions (or at least tries to)
def get_transactions(account, transactions):
   parsed_transactions = []
   pending_hashes = {} #avoid dupes
   for transaction in transactions:
      txn_hash = transaction['hash']
      if txn_hash in pending_hashes.keys():
         continue #dupes
      status = transaction['status']
      if status == 'cleared':
         pending_hashes[txn_hash] = txn_hash
         #print(transaction)
         txn_type = transaction['type']
         txn = transaction['txn']
         #print(txn)
         update_time = transaction['updated_at']         
         amount = 0
         if 'amount' in transaction.keys():
            amount = transaction['amount']
         fee = 0
         if 'fee' in transaction.keys():
            amount = transaction['fee']
         nonce = 0
         if 'nonce' in transaction.keys():
            amount = transaction['nonce']
         payer = ''
         if 'payer' in transaction.keys():
            payer = transaction['payer']
         if txn_type =='payment_v2':             
            #print(txn)
            payer = txn['payer']
            amount = txn['payments'][0]['amount'] #assuming single payee
            fee = txn['fee']
            #print(f'{payer} {account}')
            if payer == account:
               amount = 0 - amount
               #amount = 0 #assuming we trade out later, just track fees
            else:
               fee = 0              
         elif txn_type =='payment_v1':
            #print(transaction)
            payer = txn['payer']
            amount = txn['amount']
            fee = txn['fee']
            if payer == account:
               amount = 0 - amount
               #amount = 0 #assuming we trade out later, just track fees
            else:
               fee = 0             
         elif txn_type == 'assert_location_v1':
            payer = txn['payer']
            if payer != None and payer != '' and payer != account:
               #print(f'ignoring assert paid by helium: {txn}')
               continue
            fee = txn['staking_fee']
         elif txn_type =='add_gateway_v1': #ignoring on purpose
            continue
         elif txn_type =='token_burn_v1': #ignoring on purpose
            continue
         else:
            print(f'unsupported type: {txn_type}')      
         
         msg = f'{update_time},{txn_type},{amount},{fee}'
         print(f'{msg}')
         parsed_transaction = {}
         parsed_transaction['update_time'] = update_time
         parsed_transaction['txn_type'] = txn_type
         parsed_transaction['amount'] = amount
         parsed_transaction['fee'] = fee
         parsed_transactions.append(parsed_transaction)
   return parsed_transactions
   
#this basically just strips out any fee amounts in usd to then remove from your daily tax lots later
def get_modified_transactions(account, transactions):
   modified_transactions = []
   for transaction in transactions:
      print(transaction)
      update_time = transaction['update_time']
      time_stamp = parse(update_time)
      time_stamp_adj = utc_to_local(time_stamp)
      date = time_stamp_adj.date()
      amount = 0
      fee = transaction['fee'] 
      mod_transaction = {}
      mod_transaction['update_time'] = date
      txn_type = transaction['txn_type']
      fee_divisor = 100000 #convert to USD
      if txn_type == 'payment_v1':
         amount = (0 - fee) / fee_divisor
      elif txn_type == 'payment_v2':
         amount = (0 - fee) / fee_divisor
      elif txn_type == 'assert_location_v1':
         amount =  (0 - fee) / fee_divisor
      mod_transaction['usd_amount'] = amount
      if amount != 0:
         modified_transactions.append(mod_transaction)
   print(modified_transactions)
   return modified_transactions    

def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)

if __name__ == '__main__':
    parser = argparse.ArgumentParser("tax tools")
    parser.add_argument('-x', choices=['refresh_hotspots','hnt_rewards', 'tax_lots', 'parse_trades', 'schedule_d'], help="action to take", required=True)
    parser.add_argument('-n', '--name', help='hotspot name to analyze with dashes-between-words')
    parser.add_argument('-f', '--file', help='data file for tax processing')
    args = parser.parse_args()
    H = Hotspots()
    hotspots = []
    if args.name:
        names = args.name.split(',')
        for name in names:
           hotspot = H.get_hotspot_by_name(name)
           if hotspot is None:
              raise ValueError(f"could not find hotspot named '{name}' use dashes between words")
           hotspots.append(hotspot)

    if args.x == 'refresh_hotspots':
        load_hotspots(True)
    if args.x == 'hnt_rewards':
        load_hnt_rewards(hotspots)
    if args.x =='tax_lots':
        load_tax_lots(hotspots)
    if args.x == 'parse_trades':
        parse_trades(args.file)
    if args.x =='schedule_d':
        process_trades(hotspots, args.file)
