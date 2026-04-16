# studious-lamp

Quantitative midcap stock ranking tool. Runs in [Pythonista](http://omz-software.com/pythonista/) on iPhone/iPad.

## Setup

1. Copy `app.py` and `tickers.txt` into Pythonista
2. Edit `tickers.txt` with your tickers (one per line)
3. Open `app.py` and tap **Run**

No extra packages needed — uses only `requests` (built into Pythonista).

## What it does

Pulls closing prices from Yahoo Finance for every ticker in `tickers.txt` and prints a ranked table sorted by 1-month price change.
