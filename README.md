# Topographic Art Generator for Blender

A Blender add-on that generates 3D topographic terrain artwork, contour lines, base plates, and studio lighting setups using custom procedural noise algorithms.

## Features

* **Procedural Terrain Generation:** Native, multi-scale 2D value noise implementation with full control over scale, resolution, height, and surface complexity.
* **Marching Squares Contour Lines:** Precise extraction of 3D contour lines generated directly from terrain height grids.
* **Customizable Base Plate:** Beveled base plate with customizable dimensions, thickness, and bevel radius.
* **Material Customization:** Pre-configured materials for the terrain surface, contour lines, base plate, and side walls.
* **Studio Scene Setup:** Automatic generation of orthographic camera angles and dual-light soft studio lighting.
* **Transform Preservation:** Regenerating or randomizing terrain retains any existing translation, rotation, and scaling applied to the root object.

---

## Installation from GitHub

Blender requires downloading the repository files to your local machine prior to installation. Choose one of the two methods below:

### Method 1: Installing via GitHub Repository ZIP (Recommended)

1. Click the green **`<> Code`** button at the top right of this repository page and select **Download ZIP**.
2. Open Blender (**v4.0+** or **v5.2+** recommended).
3. Go to **Edit > Preferences > Add-ons**.
4. Click the arrow icon at the top right of the Add-ons panel and select **Install from Disk...** (or click the **Install...** button in earlier Blender versions).
5. Select the downloaded `.zip` file.
6. Search for **"Topographic Art Generator"** in the search box and check the box next to it to enable the add-on.

### Method 2: Installing via Direct `.py` File

1. Navigate to `topo_script.py` in this repository.
2. Click the **Raw** button on the top right of the code view.
3. Press `Ctrl + S` (or `Cmd + S` on Mac) to save the file to your computer as `topo_script.py`.
4. In Blender, go to **Edit > Preferences > Add-ons > Install...** (or **Install from Disk...**).
5. Select `topo_script.py` and check the box to enable **Topographic Art Generator**.

---

## Usage

1. Open the **3D Viewport** in Blender.
2. Open the Sidebar by pressing `N` on your keyboard.
3. Select the **Topo** tab on the side panel.
4. Adjust your desired parameters under **Terrain**, **Contours**, **Base Plate**, and **Materials**.
5. Click **Generate / Regenerate** to build the 3D topographic artwork in your scene.

---

## UI Parameters

### Terrain

* **Width / Depth / Height:** World-space dimensions of the generated terrain.
* **Resolution:** Resolution of the height grid mesh. Higher values produce smoother terrain and detailed contours at the cost of processing time.
* **Complexity:** Number of noise octave layers applied to shape the surface details.

### Randomization

* **Seed:** Integer seed for deterministic terrain shapes.
* **Randomize Seed:** Generates a new random seed and instantly regenerates the model.

### Contours

* **Contour Count:** Total number of contour elevation levels to derive across the terrain height.
* **Line Thickness:** Bevel radius of the extracted 3D curve paths.

### Base Plate & Materials

* **Base Thickness & Margin:** Controls base plate depth and surrounding border dimensions.
* **Base Bevel:** Edge rounding applied to the base plate via a bevel modifier.
* **Color & Roughness Inputs:** Direct real-time controls for surface, line, side wall, and base materials. Click **Update Materials** to apply color adjustments without re-computing geometry.

### Scene Setup

* **Create Camera & Lights:** Toggles orthographic camera placement along with key and fill area lights.
* **Key / Fill Light Power:** Adjusts wattage settings for scene lights.

---

## Project Structure

When generated, the add-on builds a structured hierarchy under a dedicated collection named `Topographic Art`:

```text
Topographic Art (Collection)
 └── Topo Root (Empty)
      ├── Topo Terrain (Mesh)
      ├── Topo Base (Mesh)
      ├── Topo Contour XX (Curves)
      ├── Topo Camera (Camera)
      ├── Topo Key Light (Light)
      └── Topo Fill Light (Light)
```

---

## Requirements

* **Blender Version:** Blender 4.0 or newer
* **License:** GPL-3.0
