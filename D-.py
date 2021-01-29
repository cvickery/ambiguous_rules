from collections import Counter

colleges = dict()
for term in ['1199', '1209']:
  colleges[term] = Counter()
  with open(f'./{term}_D-.txt') as infile:
    for line in infile.readlines():
      fields = line.split()
      if line[-8] == 'Y' and fields[10] == fields[11]:
        colleges[term][line[-6:-3]] += 1

for college in sorted(colleges["1199"].keys()):
  print(f'{college} {colleges["1199"][college]:>6,} {colleges["1209"][college]:>6,}')
