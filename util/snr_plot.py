import argparse
import matplotlib.pyplot as plt
import math
from collections import defaultdict
import numpy as np
from pathlib import Path


def run(file):
    maxsnr = 100
    with open(file) as f:
        body = False
        bls = defaultdict(list)
        for l in f:
            l = l.strip()
            if body:
                if l.endswith("false"):
                    pass
                tmp = l.split()
                sta = "-".join(sorted(tmp[1].split("-")))
                bls[sta].append(float(tmp[8]))
            if l.startswith("scan"):
                body = True
    ncols = 6
    nrows = math.ceil(len(bls) / ncols)

    fig, axs = plt.subplots(nrows, ncols, figsize=(ncols, nrows * 2), sharex=True, sharey=True)
    for ax, (bl, snrs) in zip(axs.flat, bls.items()):
        plt.sca(ax)
        plt.text(0.5, 1.0, bl, ha='center', va='top', transform=ax.transAxes)
        data = np.array(snrs)
        data[data > maxsnr] = maxsnr
        plt.violinplot(data)
        plt.grid(True, color='gray', linestyle=':', alpha=0.5)
        plt.axhline(15, color='black', linestyle='--', alpha=0.5)
        pass
    plt.xticks([])
    plt.ylim(0, maxsnr * 1.1)
    fig.supylabel('SNR')
    plt.tight_layout()
    plt.savefig(file.parent / "snr.png", dpi=150)
    pass


if __name__ == "__main__":
    doc = "Plots a uv plot of all sources. The plots will be stored under path_to_skd/uv/*.png."

    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument("-file", help="path to input .snr file")
    args = parser.parse_args()

    run(Path(args.file))
