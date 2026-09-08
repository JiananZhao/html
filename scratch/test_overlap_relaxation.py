import sys
sys.path.insert(0, r"E:\AI\Github_AIProject\html")
import numpy as np
from quant_models import calculate_cicc_sector_quadrant

df = calculate_cicc_sector_quadrant()
print(f"Loaded {len(df)} records.")

def map_coords(odds, win):
    x = ((odds - 50.0) / 50.0) * 80.0
    y = ((win - 50.0) / 50.0) * 54.0
    return x, y

items = []
for idx, row in df.iterrows():
    ticker = str(row['ticker'])
    odds = float(row['odds_score'])
    win = float(row['win_score'])
    comp = float(row['composite_score'])
    normScore = max(0.0, min(1.0, (comp - 20.0) / 75.0))
    r = 1.8 + normScore * 1.6
    x, y = map_coords(odds, win)
    items.append({'ticker': ticker, 'x': x, 'y': y, 'orig_x': x, 'orig_y': y, 'r': r, 'odds': odds, 'win': win})

print("\n--- Before Relaxation: Pairs with distance < (r1+r2)*1.18 ---")
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        p1, p2 = items[i], items[j]
        d = np.hypot(p1['x'] - p2['x'], p1['y'] - p2['y'])
        min_dist = (p1['r'] + p2['r']) * 1.18
        if d < min_dist:
            print(f"{p1['ticker']} (r={p1['r']:.2f}) <-> {p2['ticker']} (r={p2['r']:.2f}): dist = {d:.2f} < min_dist = {min_dist:.2f} (OVERLAP!)")

# Apply relaxation
for _ in range(20):
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            p1, p2 = items[i], items[j]
            dx = p2['x'] - p1['x']
            dy = p2['y'] - p1['y']
            d = np.hypot(dx, dy) or 0.001
            min_dist = (p1['r'] + p2['r']) * 1.18
            if d < min_dist:
                overlap = (min_dist - d) * 0.52
                nx, ny = dx / d, dy / d
                p1['x'] -= nx * overlap
                p1['y'] -= ny * overlap
                p2['x'] += nx * overlap
                p2['y'] += ny * overlap

print("\n--- After Relaxation: Check again ---")
overlapping_after = 0
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        p1, p2 = items[i], items[j]
        d = np.hypot(p1['x'] - p2['x'], p1['y'] - p2['y'])
        min_dist = (p1['r'] + p2['r']) * 1.18
        if d < min_dist:
            print(f"Still close: {p1['ticker']} <-> {p2['ticker']}: dist = {d:.2f} < min_dist = {min_dist:.2f}")
            overlapping_after += 1

print(f"Total overlapping pairs after: {overlapping_after}")
for item in items:
    if item['ticker'] in ['XLRE', 'XLU', 'XLK', 'SMH']:
        print(f"{item['ticker']}: orig=({item['orig_x']:.2f}, {item['orig_y']:.2f}) -> relaxed=({item['x']:.2f}, {item['y']:.2f}) [odds={item['odds']}, win={item['win']}]")
