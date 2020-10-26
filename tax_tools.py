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

def load_hnt_rewards(hotspot, use_realtime_oracle_price=True, num_tax_lots=10000):
    tax_lots = load_api_rewards(hotspot,use_realtime_oracle_price,num_tax_lots)
    print("Got: {len(tax_lots)} lots")
    f = open(f"data/{hotspot['name']}.csv", "w")
    for tax_lot in reversed(tax_lots):
        as_of_time = tax_lot['timestamp']
        amount = tax_lot['amount']
        block = tax_lot['block']
        oracle_price = 0
        #oracle_price = load_oracle_price_at_block(block)['price']
        print(f"{as_of_time},{amount},{oracle_price},{block}")
        f.write(f"{as_of_time},{amount},{oracle_price},{block}\n")
    f.close()

def load_api_rewards(hotspot, use_realtime_oracle_price=True, num_tax_lots=10000):
    cursor = None
    tax_lots = []
    address = hotspot['address']
    first_block = hotspot['block_added']
    max_date = datetime.now() + timedelta(days=1) #mostly for UTC nonsense
    max_time = max_date.date().isoformat()
    min_date = get_block_date_time(first_block).date()
    min_date = min_date - timedelta(days=1) #mostly for UTC nonsense
    min_time = min_date.isoformat()
    print(max_time)
    print(min_time)
    if num_tax_lots > 50000:
        raise ValueError(f"invalid number of rewards to load")
    while len(tax_lots) < num_tax_lots:
        path = f"hotspots/{address}/rewards?max_time={max_time}&min_time={min_time}"
        print(path)
        if cursor:
            path += f"&cursor={cursor}"
        result = api_call(path=path)
        print(f"-I- loaded {len(result['data'])} rewards")
        cursor = result.get('cursor')

        tax_lots.extend(result['data'])
        if not cursor:
            break
        #print(tax_lots)

    return tax_lots

def load_tax_lots(hotspot):
    filename = f"data/{hotspot['name']}.csv"
    file_exists = path.exists(filename)
    if file_exists != True:
        load_hnt_rewards(hotspot)
    prices_by_date = get_hnt_open_prices()
    print(prices_by_date)
    day_lots = consolidate_day_lots(filename)
    return output_tax_lots_by_day(hotspot, day_lots, prices_by_date)


def output_tax_lots_by_day(hotspot, day_lots, prices_by_date):
    tax_lots = []
    hnt_adjust = 100000000 #divisor for hnt value rep
    total_hnt = 0
    total_usd = 0
    hotspot_name = hotspot['name']
    f = open(f"output/{hotspot_name}_tax_lots.csv", "w")
    print(f'date,hotspot,hnt_amount,hnt_price,usd_amount')
    f.write(f'date,hotspot,hnt_amount,hnt_price,usd_amount\n')
    for key in day_lots:
        date = key
        hnt_amount = day_lots[key]
        hnt_amount_adj = hnt_amount / hnt_adjust
        hnt_price = 0
        if date in prices_by_date:
            hnt_price = prices_by_date[date]
        usd_amount = (hnt_amount * hnt_price) / hnt_adjust
        total_hnt += hnt_amount_adj
        total_usd += usd_amount
        print(f'{date},{hotspot_name},{hnt_amount_adj},{hnt_price},{usd_amount}')
        f.write(f'{date},{hotspot_name},{hnt_amount_adj},{hnt_price},{usd_amount}\n')
        tax_lot = {}
        tax_lot['time'] = date
        tax_lot['hnt_amount'] = hnt_amount_adj
        tax_lot['hnt_price'] = hnt_price
        tax_lots.append(tax_lot)

    print(f'Total HNT: {total_hnt}, Total USD: {total_usd}')
    return tax_lots

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
            print(time_stamp)
            print(time_stamp_adj)
            date_stamp = time_stamp_adj.date() #handle timezone?
            amount = int(row[1])
            block = row[2]
            print(f'{time_stamp}, {date_stamp}: {amount}')

            if date_stamp in amounts_by_date.keys():
                amounts_by_date[date_stamp] += amount
            else:
                amounts_by_date[date_stamp] = amount
            total += amount

    print(f'Processed {line_count} lines.')
    print(amounts_by_date)
    print(f'Total: {total}')
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

def process_trades(hotspot, filename):
   trades = parse_trades(filename)
   tax_lots = load_tax_lots(hotspot)
   schedule_d_items = get_schedule_d(tax_lots, trades)
   output_schedule_d(schedule_d_items)


def get_schedule_d(tax_lots, trades):
   schedule_d_items = []
   total_gain_loss = 0
   for trade in reversed(trades): #order by time
      trade_time = trade['time']
      trade_hnt_price = trade['hnt_price']
      remaining_amount = trade['hnt_amount']
      for tax_lot in tax_lots: #order by time (FIFO only now)
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
   print(total_gain_loss)
   #print(schedule_d_items)
   return schedule_d_items

def output_schedule_d(items):
    f = open(f"output/schedule_d.csv", "w")
    msg = f'open_time,close_time,open_price,close_price,gain_loss'
    print(f'{msg}')
    f.write(f'{msg}\n')
    for item in items:
       open_time = item['open_time']
       close_time = item['close_time']
       open_price = item['open_price']
       close_price = item['close_price']
       gain_loss = item['gain_loss']
       msg = f'{open_time},{close_time},{open_price},{close_price},{gain_loss}'
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
    hotspot = None
    if args.name:
        hotspot = H.get_hotspot_by_name(args.name)
        if hotspot is None:
            raise ValueError(f"could not find hotspot named '{args.name}' use dashes between words")

    if args.x == 'refresh_hotspots':
        load_hotspots(True)
    if args.x == 'hnt_rewards':
        load_hnt_rewards(hotspot)
    if args.x =='tax_lots':
        load_tax_lots(hotspot)
    if args.x == 'parse_trades':
        parse_trades(args.file)
    if args.x =='schedule_d':
        process_trades(hotspot, args.file)
