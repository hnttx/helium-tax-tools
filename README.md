# helium-tax-tools
Basic tools for creating mined tax lots (using a source file that is currently coming from coingecko but can be modified as appropriate).

This is heavily derived from https://github.com/Carniverous19/helium_analysis_tools/ , thanks to Carniverous19

# Installation
To install simply run

    git clone https://github.com/hnttx/helium-tax-tools.git


# Tools
python3 tax_tools.py -x tax_lots -n animal-name-spaces -y 2020

where animal-name-spaces is the name of your hotspot. Update: can also be a comma separated list of multiple hotspots by animal names
y is the tax year

This will refresh all hotspots, retrieve all of your rewards and save them in data/animal-name-spaces.csv, then output your consolidated tax lots by day in output/animal-name-spaces_tax_lots.csv


python3 tax_tools.py -x hnt_rewards -n animal-name-spaces

this will refresh the cached rewards data that is used in tax_lots


python3 tax_tools.py -x schedule_d -n animal-name-spaces -f binances-trades.csv -y 2020
y is the tax year

This will read a binance exported csv file and combine the trades from there with your tax lots to produce a basic schedule D output in output subdirectory.


# Expected Binance CSV format

Date(UTC),Market,Type,Price,Amount,Total,Fee,Fee Coin
* It currently does't care about the fees at all.



# Known issues
The cost data is only post 4/18/2020, with manual updates in hnt-prices/hnt-prices.csv

I defaulted 1/1/2020 - 4/17/2020 with 0.15 (adjust as you see fit), I'm not a tax lawyer. 

If your hotspot predates that, you will need to make adjustments certainly. Especially if you carried basis from 2019.

To Do: support other exchange formats, improve schedule D functionality, support HNT buying activity properly

# Disclaimer
Use at your own risk. I am not an accountant and take no responsibility for these tools or your taxes.

# Donations
For those interested, you can send HNT to: 13HMBycBt4XWkKVqREVbw1LWxx1cuaAhfZ1TkVwvSCxydRePXMy
