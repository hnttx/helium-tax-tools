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

def load_tax_lots(hotspot, time_zone_adjust=-4):
    filename = f"data/{hotspot['name']}.csv"
    file_exists = path.exists(filename)
    if file_exists != True:
        load_hnt_rewards(hotspot)    
    prices_by_date = get_hnt_open_prices()
    print(prices_by_date)
    day_lots = consolidate_day_lots(filename, time_zone_adjust)
    output_tax_lots_by_day(hotspot, day_lots, prices_by_date)


def output_tax_lots_by_day(hotspot, day_lots, prices_by_date):
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

    print(f'Total HNT: {total_hnt}, Total USD: {total_usd}')

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
def consolidate_day_lots(filename, time_zone_adjust):
    print(f'reading from {filename}')
    amounts_by_date = {}
    total = 0
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            time_stamp_str = row[0]
            time_stamp = parse(time_stamp_str)
            tz_delta = timedelta(hours = time_zone_adjust)
            time_stamp_adj = time_stamp + tz_delta
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

def get_block_date_time(block):
    path = f"blocks/{block}"
    result = api_call(path=path)
    print(result)
    time = result["data"]["time"]
    as_of_time = datetime.fromtimestamp(time)
    print(as_of_time)
    return as_of_time

if __name__ == '__main__':
    parser = argparse.ArgumentParser("tax tools")
    parser.add_argument('-x', choices=['refresh_hotspots','oracle_prices','hnt_rewards', 'tax_lots'], help="action to take", required=True)
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
    if args.x == 'oracle_prices':
        load_blocks(True)
    if args.x == 'hnt_rewards':
        load_hnt_rewards(hotspot)
    if args.x =='tax_lots':
        load_tax_lots(hotspot)
