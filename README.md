# helium-tax-tools
Basic tools for creating mined tax lots (using a source file that is currently coming from coingecko but can be modified as appropriate).

This is heavily derived from https://github.com/Carniverous19/helium_analysis_tools/ , thanks to Carniverous19

# Installation
To install simply run

    git clone https://github.com/hnttx/helium-tax-tools.git


# Tools
python3 tax_tools.py -x tax_lots -n animal-name-spaces

where animal-name-spaces is the name of your hotspot.

This will refresh all hotspots, retrieve all of your rewards and save them in data/animal-name-spaces.csv, 
then output your consolidated tax lots by day in output/animal-name-spaces_tax_lots.csv

# Disclaimer
Use at your own risk. I am not an accountant and take no responsibility for these tools or your taxes.
