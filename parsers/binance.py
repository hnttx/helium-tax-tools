import csv
from dateutil.parser import parse
from decimal import Decimal, getcontext
from parsers.parser_utils import utc_to_local

def parse_binance_trades(filename):
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
            market = row[1]
            if not market.startswith('HNT'):
                raise Exception(f'unexpected product in binance trades file: {market}', f'{market} not supported')
            buy_sell = row[2]
            time_stamp = parse(time_stamp_str)
            time_stamp_adj = utc_to_local(time_stamp)
            hnt_price = Decimal(row[3])
            hnt_amount = Decimal(row[4])
            cash_total = Decimal(row[5])
            fee = Decimal(row[6])
            fee_coin = row[7]
            if fee_coin.upper().startswith('USD'):
                cash_total -= fee
                orig_hnt_price = hnt_price
                hnt_price = cash_total / hnt_amount
                print(f'before price:{orig_hnt_price} adj: {hnt_price}')
            elif fee_coin.upper().startswith('HNT'):
                hnt_amount -= fee

            if buy_sell.startswith('B'):
                print(f'buy detected {hnt_amount}')
                hnt_amount = 0 - hnt_amount #treat as buy
            trade = {}
            trade['time'] = time_stamp_adj
            trade['hnt_price'] = hnt_price
            trade['hnt_amount'] = hnt_amount
            trade['exchange'] = 'binance' #support others later
            trades.append(trade)
#    print(trades)
    return trades

#primitive detection of binace export format using header
def is_binance_file(filename):
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0;
        for row in csv_reader:
            if "Market" in row and "Fee Coin" in row:
                print(f'{row}')
                return True
            else:
                return False

