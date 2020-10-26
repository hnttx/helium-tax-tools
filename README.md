# helium-tax-tools
Basic tools for creating mined tax lots (using a source file that is currently coming from coingecko but can be modified as appropriate).

This is heavily derived from https://github.com/Carniverous19/helium_analysis_tools/ , thanks to Carniverous19

# Installation
To install simply run

    git clone https://github.com/hnttx/helium-tax-tools.git


# Tools
python3 tax_tools.py -x tax_lots -n animal-name-spaces

where animal-name-spaces is the name of your hotspot.

python3 tax_tools.py -x hnt_rewards -n animal-name-spaces

this will refresh the cached rewards data that is used in tax_lots


This will refresh all hotspots, retrieve all of your rewards and save them in data/animal-name-spaces.csv, 
then output your consolidated tax lots by day in output/animal-name-spaces_tax_lots.csv

# Known issues
The cost data is only 4/18/2020 - 10/24/2020 currently, can update that in data/hnt-prices.csv

If your hotspot predates that, you will need to make adjustments certainly. Especially if you carried basis from 2019.

To Do: support sell transactions (from exchanges) to create schedule D, probalby using FIFO.

# Disclaimer
Use at your own risk. I am not an accountant and take no responsibility for these tools or your taxes.

# Donations
For those interested, you can send HNT to: 13HMBycBt4XWkKVqREVbw1LWxx1cuaAhfZ1TkVwvSCxydRePXMy
