console.log("hello!!!!!!!!!!!!!!!")


function autoComplete(locParam, API_URL)
{
	loc = document.querySelectorAll(locParam)
console.log(loc)
for (lo of loc) {
	lo.addEventListener('input', async (e) =>  {
		console.log(e)
		console.log(e.target.value)
		if (e.target.value == null) {
			return
		}
		if (e.target.value.length < 2) {
			return
		}
		resp = await fetch(API_URL)
		console.log(resp)
		console.log(resp.status)
		switch (resp.status) {
		case 200:
			console.log(await resp.json())
			break
		}
	}
	)
}
}
autoComplete('.location', "/api/locations/search")
autoComplete('.tag', "/api/tags/search")

add_item_group_button = document.querySelector("#addItemGroupButton")
add_item_button = document.querySelector("#addItemButton")
add_location_button = document.querySelector("#addLocationButton")
