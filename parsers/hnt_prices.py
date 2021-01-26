import csv
from dateutil.parser import parse
from decimal import Decimal, getcontext
from parsers.parser_utils import utc_to_local

def get_hnt_open_prices(filename ='hnt-prices/hnt-prices.csv'):
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
            price = Decimal(price_str)
            prices_by_date[date_stamp] = price
    return prices_by_date
