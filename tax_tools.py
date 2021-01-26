import json
import urllib.request
import urllib.error
import time
import argparse
import datetime
import csv
import os.path
from os import path
from utils import load_hotspots, api_call
from dateutil.parser import parse
from classes.Hotspots import Hotspots
from datetime import datetime
from datetime import timedelta
from decimal import Decimal, getcontext
from tax_lots import aggregate_mining_lots_by_day, get_tax_lots_from_buy_trades, get_schedule_d
from tax_tool_writers import write_hnt_rewards, write_tax_lots, write_schedule_d
from parsers.hnt_prices import get_hnt_open_prices
from parsers.binance import parse_binance_trades, is_binance_file
from parsers.heliumex_db import parse_heliumex_db_trades, is_heliumex_db_file
from parsers.parser_utils import utc_to_local

g_hnt_adjust = Decimal(100000000) #divisor for hnt value rep
g_include_transaction_fees = False #experimental, toggle on to try to include txn fees/assert location fees

def load_hnt_rewards(hotspot, use_realtime_oracle_price=True, num_rewards=10000):
   for hotspot in hotspots:
      rewards = load_api_hotspot_rewards(hotspot,use_realtime_oracle_price,num_rewards)
      write_hnt_rewards(hotspot, rewards)

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

def load_tax_lots(hotspots, year):
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
      hotspot_day_lots = aggregate_mining_lots_by_day(filename)
      hotspot_tax_lots = write_tax_lots_by_day(hotspot, hotspot_day_lots, account_transactions, prices_by_date, year)
      tax_lots.extend(hotspot_tax_lots)
   total_hnt = Decimal(0)
   total_usd = Decimal(0)
   for tax_lot in tax_lots:
       total_hnt += tax_lot['hnt_amount']
       total_usd += tax_lot['usd_amount']
   print(f'Total HNT (all hotspots): {total_hnt}, Total USD: {total_usd}')
   return tax_lots

def write_tax_lots_by_day(hotspot, day_lots, account_transactions, prices_by_date, year):
    tax_lots = []
    total_hnt = Decimal(0)
    total_usd = Decimal(0)
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
        if year > 0 and date.year != year:
            continue
        hnt_fees = Decimal(0)

        hnt_price = Decimal(0)
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
        dt = datetime.combine(date, datetime.min.time())
        tax_lot['time'] = dt
        tax_lot['hotspot'] = hotspot_name
        tax_lot['hnt_amount'] = hnt_amount_adj
        tax_lot['hnt_price'] = hnt_price
        tax_lot['usd_amount'] = usd_amount
        tax_lots.append(tax_lot)
        #print(f"{tax_lot}")
    write_tax_lots(tax_lots, filename)

    print(f'Total HNT: {total_hnt}, Total USD: {total_usd}')
    return tax_lots

def parse_trades(filenames):
    filename_array = filenames.split(',')
    trades = []
    for filename in filename_array:
        if is_binance_file(filename):
            trades.extend(parse_binance_trades(filename))
        elif is_heliumex_db_file(filename):
            trades.extend(parse_heliumex_db_trades(filename))
        else:
            raise Exception(f'could not detect {filename} as a supported tranasaction file', f'{filename} not supported')
    return trades

def process_trades(hotspots, filename, year):
   trades = parse_trades(filename)
   tax_lots = load_tax_lots(hotspots, year)
   result =  get_schedule_d(tax_lots, trades)
   schedule_d_items = result[0]
   remaining_tax_lots = result[1]
   write_schedule_d(schedule_d_items)
   filename = 'output/remaining_tax_lots.csv'
   write_tax_lots(remaining_tax_lots, filename)

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
         amount = Decimal(0)
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
      amount = Decimal(0)
      fee = transaction['fee'] 
      mod_transaction = {}
      mod_transaction['update_time'] = date
      txn_type = transaction['txn_type']
      fee_divisor = Decimal(100000) #convert to USD
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser("tax tools")
    parser.add_argument('-x', choices=['refresh_hotspots','hnt_rewards', 'tax_lots', 'parse_trades', 'schedule_d'], help="action to take", required=True)
    parser.add_argument('-n', '--name', help='hotspot name to analyze with dashes-between-words')
    parser.add_argument('-f', '--file', help='data file(s) for tax processing')
    parser.add_argument('-y', '--year', help='filter to a given tax year')
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
    year = -1
    if args.year:
        year = int(args.year)
        print(f"running for tax year: {year}")

    if args.x == 'refresh_hotspots':
        load_hotspots(True)
    if args.x == 'hnt_rewards':
        load_hnt_rewards(hotspots)
    if args.x =='tax_lots':
        load_tax_lots(hotspots, year)
    if args.x == 'parse_trades':
        parse_trades(args.file)
    if args.x =='schedule_d':
        process_trades(hotspots, args.file, year)
