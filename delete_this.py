from pathlib import Path
from rsge_toolbox.lidar import Laszy

json_path = R'F:\_Olena_\QC\2022-2023\OP23BMRS014_Production\3rd_delivery_27Mar_2023\tests\LiQCS\laszy_json'

outdir = R'F:\_Olena_\QC\2022-2023\OP23BMRS014_Production\3rd_delivery_27Mar_2023\tests\LiQCS\out'

p = Path(json_path).rglob('*.json')
files = [f.__str__() for f in p]

# print(files)


rep = Laszy.LaszyReport(files, outdir=outdir)
rep.write(validate=True)

