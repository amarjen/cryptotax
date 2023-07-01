# cryptotax
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This tool will help you to compute the PNL of your crypto trades based on FIFO accounting method for tax purposes.

It reads transactions from CSV files and process them to output a PNL report. It's types are:
- BUY: Buy an asset againts base fiat currency.
- BUY PERMUTA: Buy a crypto asset against another crypto primary asset.
- SELL: Sell an asset for base fiat currency.
- SELL PERMUTA: Sell a crypto asset for another crypto primary asset.

## Definitions
- **Base Fiat Asset:** Eg. `EUR` / `USD` / ... The tool will not track inventory for this asset.
- **Crypto Asset:** Any asset you trade, save Fiat assets. The tool will track balances for this kind of assets, in order to compute PNL.
- **Primary Crypto Asset:** The ones you have available its prices quoted in `base_fiat_asset`. Currently the tool only allows `BTC`

## Installation
Not yet: `python -m pip install cryptotax`

```
git clone https://github.com/amarjen/seed-shuffler.git
cd seed-shuffler
python -m pip install .
```

## Usage
`cryptotax --year YEAR`

## Tests
Just run `pytest` from the project folder.

## Contributing
TODO

## License
This project is licensed under the terms of the MIT license.
