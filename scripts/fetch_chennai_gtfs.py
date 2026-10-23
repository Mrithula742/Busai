"""Install the published Chennai MTC static feed into the local GTFS directory."""
import io
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

SOURCE = 'https://github.com/ungalsoththu/ChennaiGTFS/raw/refs/heads/main/data/mtc-gtfs.zip'
DESTINATION = Path(__file__).resolve().parents[1] / 'datasets' / 'gtfs'

if __name__ == '__main__':
    with urlopen(SOURCE, timeout=90) as response:
        archive = ZipFile(io.BytesIO(response.read()))
    files = {Path(name).name: archive.read(name) for name in archive.namelist() if name.endswith('.txt')}
    required = {'routes.txt', 'stops.txt', 'trips.txt', 'stop_times.txt'}
    if not required.issubset(files):
        raise ValueError('Downloaded archive is missing required GTFS files')
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (DESTINATION / name).write_bytes(data)
    print(f'Installed {len(files)} GTFS files in {DESTINATION}')
