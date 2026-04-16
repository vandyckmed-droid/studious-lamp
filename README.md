# studious-lamp

Quantitative midcap stock ranking tool. Runs in [Pythonista](http://omz-software.com/pythonista/) on iPhone/iPad.

## Setup (one time)

1. Open Pythonista
2. Install StaSh (a terminal for Pythonista) — tap **+** > **Script**, paste this, and run it:
   ```python
   import requests as r; exec(r.get('https://bit.ly/get-stash').text)
   ```
3. Restart Pythonista
4. Open `launch_stash.py` and run it
5. In StaSh, type: `pip install yfinance`
6. Clone this repo or copy the files into Pythonista

## Usage

1. Edit `tickers.txt` with your universe (one ticker per line)
2. Run `app.py`
3. See a ranked table of stocks sorted by 1-month price change
