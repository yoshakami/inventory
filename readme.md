# Inventory
A responsive web page written in native html, css, and js. The backend is written in python.

# Usage
You need to edit db.py with your database. you can use sqlite with the example provided below <br>
You also need to create the file "users.json" <br>
here's a minimal example. You can add more users, but you still need at least server and Yosh, unless you edit the constants at the top of app.py.
```
{
    "Yosh": "Yosh_password",
    "server": "flask_password"
}
```
once you're setup, you can start the project :
```
pip install -r requirements.txt
python app.py
```
# Adding
Add a Item Group First (e.g. Pro Controller) <br>
then add as many items linked to that group. as long as the ID box is empty, it'll add a new item. 
 
# Editing
If the ID box corresponds to an existing item, it will edit it. <br>
If you already made an Item Group with the same name, you can edit every attributes except its name. <br>
If you change the name of an Item Group, the app will create a new one instead. <br>
You'd then need to click on the pencil icon on every item of the previous Group and assign it to the new Item Group

# Notes
Empty Item Groups are not shown on the results panel. <br>
<br>
You can disable Autocomplete if you want to. This button appears when the window is small enough.<br>
<br>
Items with the Tag +18 are not shown if you're not Yosh, or if the Yosh button is red. This button appears when the window is small enough.

# Furniture photos ("ici jamy!!!!")
Upload one photo per pile of furniture (Kallax, drawer unit 1, drawer unit 2, …) in the **Location** card. Search an item, then click **ici jamy!!!!** — every pile is shown, and the matching compartment gets a red box plus a huge arrow.

## Color mask (no AI)
1. Create the location for the furniture (e.g. `Kallax`) and child locations for each cube/drawer (`Kallax 1`, `Kallax 2`, … — the trailing number is used for auto-link).
2. Photograph the furniture from the front.
3. In GIMP/Photoshop, add an empty layer and fill each compartment with a unique hex color:
   - Case 1 = `#000001`
   - Case 2 = `#000002`
   - Case 54 = `#000036`
4. Hide the photo layer, export the color layer as PNG (transparent / `#000000` = ignored).
5. Upload the photo (and the mask) on that furniture location.

You can also generate the JSON yourself:

```
pip install Pillow
python mask_to_zones.py mask.png -o zones.json
```