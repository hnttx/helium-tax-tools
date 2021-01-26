import csv
from decimal import Decimal, getcontext

def write_hnt_rewards(hotspot, rewards):
      f = open(f"data/{hotspot['name']}.csv", "w")
      unique_blocks = {} #hack to remove dupe rewards
      for reward in reversed(rewards):
         as_of_time = reward['timestamp']
         amount = reward['amount']
         block = reward['block']
         if block in unique_blocks:
             continue
         unique_blocks[block] = True
         oracle_price = 0
         #oracle_price = load_oracle_price_at_block(block)['price']
         print(f"{as_of_time},{amount},{oracle_price},{block}")
         f.write(f"{as_of_time},{amount},{oracle_price},{block}\n")
      f.close()

def write_tax_lots(tax_lots, filename):
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

def write_schedule_d(items, filename = "output/schedule_d.csv"):
    f = open(filename, "w")
    msg = f'open_time,close_time,quantity,open_price,close_price,gain_loss,gain,loss,longshort'
    print(f'{msg}')
    f.write(f'{msg}\n')
    for item in items:
       open_time = item['open_time']
       close_time = item['close_time']
       quantity = item['quantity']
       open_price = item['open_price']
       close_price = item['close_price']
       gain_loss = item['gain_loss']
       gain = Decimal(0)
       loss = Decimal(0)
       if gain_loss >= 0:
           gain = gain_loss
       else:
           loss = gain_loss
       longshort = 'short' #default short
       diff_days = (close_time.date() - open_time.date()).days
       if diff_days >= 365:
           longshort = 'long'
       if diff_days < 0:
             raise Exception(f'tax lot processing resulted in scheduled d close {close_time} before open {open_time}, aborting', 'transaction order failure')
       msg = f'{open_time},{close_time},{quantity},{open_price},{close_price},{gain_loss},{gain},{loss},{longshort}'
       print(f'{msg}')
       f.write(f'{msg}\n')
