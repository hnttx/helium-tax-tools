import csv
from dateutil.parser import parse
from decimal import Decimal, getcontext
from parsers.parser_utils import utc_to_local

def parse_heliumex_db_trades(filename):
    print(f'reading trades from {filename}')
    heliumex_records = []
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0;
        for row in csv_reader:
            line_count += 1
            if (line_count == 1):
                continue
            time_stamp_str = row[2]
            transaction_type = row[3]
            if transaction_type != 'Execution' and transaction_type != 'TradingCommission':
                continue
            symbol = row[4]
            if symbol != 'USDC' and symbol != 'HNT':
                raise Exception(f'unexpected symbol {symbol} in heliumex trades file', f'{symbol} not supported')
            amount = Decimal(row[6])
            order_id = row[9]
            record = {}
            record['time'] = time_stamp_str
            record['type'] = transaction_type
            record['symbol'] = symbol
            record['amount'] = amount
            record['order_id'] = order_id
            heliumex_records.append(record)
    records_by_time = {}
    for record in heliumex_records:
        trade_record = {}
        trade_record['hnt_amount'] = Decimal(0)
        trade_record['usdc_amount'] = Decimal(0)
        trade_record = records_by_time.get(record['time'], trade_record);
        trade_record['time'] = record['time']
        if record['symbol'] == 'HNT':
            trade_record['hnt_amount'] += record['amount']
        else:
            trade_record['usdc_amount'] += record['amount']        
        records_by_time[record['time']] = trade_record

    trades = []
    for val in records_by_time.values():
        #print(f'{val}')
        trade = {}
        trade['time'] = parse(val['time'])
        trade['hnt_price'] = abs(val['usdc_amount'] / val['hnt_amount'])
        trade['hnt_amount'] = 0 - val['hnt_amount'] #bad convention
        trade['exchange'] = 'heliumex'
        print(f'{trade}')
        trades.append(trade)
    return trades

#primitive detection of heliumex db export format using header
def is_heliumex_db_file(filename):
    with open (filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0;
        for row in csv_reader:
            if "email" in row and "sequence_number" in row:
                return True
    return False

