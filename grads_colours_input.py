from grads_colours import (
    make_grads_rgb_from_colors,
    save_colourbar_from_colors,
    save_colourbar_with_values,
)
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# --- Base anchoring colours ---
base_colors = [
    "indigo", "navy", "maroon", "purple",
    "skyblue", "lightblue", "blue", "lime",
    "yellow", "orange", "red", "darkred"
]

n = 55
start_index = 71

# --- Generate GrADS RGB lines ---
lines = make_grads_rgb_from_colors(
    n=n,
    colors=base_colors,
    start_index=start_index,
)

print("'\n'".join(lines))


# ------------------------------------------------------
# --- TEMPERATURE LABELS (your set clevs)
# ------------------------------------------------------

# -80 to 52.5 every 2.5 deg gives exactly 56 numbers
temp_levels = np.arange(-80, 52.5 + 0.0001, 2.5).tolist()


# --- Build colormap identical to the RGB generation ---
cmap = LinearSegmentedColormap.from_list("custom", base_colors, N=n)


# --- Save temperature-labelled colourbar ---
save_colourbar_with_values(
    cmap=cmap,
    values=temp_levels,
    filename="temperature_colorbar.png",
    tick_step=2,      # label every 5°C (which is 2 steps of 2.5°C)
)

print("Saved temperature-labelled colourbar → temperature_colorbar.png")
