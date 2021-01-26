import csv
from dateutil.parser import parse
from decimal import Decimal, getcontext
from parsers.parser_utils import utc_to_local

#takes all transactions and consolidates them into a single tax lot per day
def aggregate_mining_lots_by_day(filename):
    print(f'reading from {filename}')
    amounts_by_date = {}
    total = Decimal(0)

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

#creates tax lots from HNT buy transactions
def get_tax_lots_from_buy_trades(buy_trades):
   sorted_buy_trades = sorted(buy_trades, key=lambda x: (x['time']))  #order by time (FIFO)
   tax_lots = []
   for trade in sorted_buy_trades: #create new tax lots for any buys
        tax_lot = {}
        time_stamp = trade['time']
        print(f'{time_stamp}')
        tax_lot['time'] = time_stamp
        tax_lot['hotspot'] = 'hntbuy'
        tax_lot['hnt_amount'] = 0 - trade['hnt_amount']
        tax_lot['hnt_price'] = trade['hnt_price']
        tax_lot['usd_amount'] = tax_lot['hnt_amount'] * tax_lot['hnt_price'] 
        tax_lots.append(tax_lot)
        print(f"{tax_lot}")
   return tax_lots

#create schedule D based on open and close transactions
def get_schedule_d(tax_lots, trades):
   schedule_d_items = []
   total_gain_loss = Decimal(0)
   remaining_tax_lots = []
   sorted_trades = sorted(trades, key=lambda x: (x['time']))  #order by time (FIFO)
   sorted_sell_trades = [x for x in sorted_trades if x['hnt_amount'] >= 0]
   sorted_buy_trades = [x for x in sorted_trades if x['hnt_amount'] < 0]
   buy_tax_lots = get_tax_lots_from_buy_trades(sorted_buy_trades)
   tax_lots.extend(buy_tax_lots)

   sorted_tax_lots = sorted(tax_lots, key=lambda x: (x['time'], x['hotspot']))

   print(f'processing {len(sorted_sell_trades)} trades.')
   for trade in sorted_sell_trades:
      print(f'{trade}')
      trade_time = trade['time']
      trade_hnt_price = trade['hnt_price']
      remaining_amount = trade['hnt_amount']
      for tax_lot in sorted_tax_lots: #order by time (FIFO only now)
         tax_lot_amount = tax_lot['hnt_amount']
         if tax_lot_amount == 0:
            continue
         tax_lot_hnt_price = tax_lot['hnt_price']
         schedule_d_amount = Decimal(0)
         schedule_d_time = trade_time
         schedule_d_gain_loss = Decimal(0)
         if tax_lot_amount > remaining_amount:
            schedule_d_amount = remaining_amount
            tax_lot_amount -= remaining_amount
            remaining_amount = Decimal(0)
         else:
            schedule_d_amount = tax_lot_amount
            remaining_amount -= tax_lot_amount
            tax_lot_amount = Decimal(0)
         if schedule_d_amount == 0:
            continue
         tax_lot['hnt_amount'] = tax_lot_amount
         schedule_d_gain_loss = schedule_d_amount * (trade_hnt_price - tax_lot_hnt_price)
         schedule_d_item = {}
         schedule_d_item['open_time'] = tax_lot['time']
         schedule_d_item['close_time'] = schedule_d_time
         schedule_d_item['quantity'] = schedule_d_amount
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
