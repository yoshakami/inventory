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
You can't edit an item group. Create a new one instead. <br>
Then click on the pencil icon on a specific item and assign it to the new Item Group

# Notes
Empty Item Groups are not shown on the results panel. <br>
<br>
You can disable Autocomplete if you want to. This button appears when the window is small enough.<br>
<br>
Items with the Tag +18 are not shown if you're not Yosh, or if the Yosh button is red. This button appears when the window is small enough.