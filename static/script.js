console.log("hello!!!!!!!!!!!!!!!")

function autoComplete(selector, API_URL) {
  const inputs = document.querySelectorAll(selector)

  inputs.forEach(input => {
    const list = input.nextElementSibling
    let activeIndex = -1
    let items = []

    function render(results) {
      list.innerHTML = ""
      activeIndex = -1
      items = results

      if (!results.length) {
        list.hidden = true
        return
      }

      results.forEach((item, i) => {
        const li = document.createElement("li")
        li.textContent = item.label

        li.addEventListener("mousedown", e => {
          e.preventDefault()
          selectItem(i) // ✅ no await here
        })

        list.appendChild(li)
      })

      list.hidden = false
    }

    async function selectItem(index) {
      const item = items[index]
      if (!item) return

      input.value = item.label
      input.dataset.id = item.id
      list.hidden = true
      list.innerHTML = ""

      // Load results panel
      const res = await fetch(
        `/api/items/search-by-tag?q=${encodeURIComponent(item.label)}`
      )
      const data = await res.json()
      console.log(data)
      renderResults(data)
    }

    function highlight() {
      [...list.children].forEach((li, i) => {
        li.classList.toggle("active", i === activeIndex)
      })
    }

    input.addEventListener("input", async e => {
      const value = e.target.value.trim()

      if (!value) {
        list.hidden = true
        list.innerHTML = ""
        return
      }

      const res = await fetch(
        `${API_URL}?q=${encodeURIComponent(value)}`
      )
      const results = await res.json()

      render(results)
    })

    input.addEventListener("keydown", async e => {
      if (list.hidden || !items.length) return

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault()
          activeIndex = Math.min(activeIndex + 1, items.length - 1)
          highlight()
          break

        case "ArrowUp":
          e.preventDefault()
          activeIndex = Math.max(activeIndex - 1, 0)
          highlight()
          break

        case "Enter":
          if (activeIndex >= 0) {
            e.preventDefault()
            await selectItem(activeIndex) // ✅ allowed here
          }
          break

        case "Escape":
          list.hidden = true
          break
      }
    })

    document.addEventListener("mousedown", e => {
      if (!input.contains(e.target) && !list.contains(e.target)) {
        list.hidden = true
      }
    })
  })
}


autoComplete('.location', "/api/locations/search")
autoComplete('.tag', "/api/tags/search")
autoComplete('.itemGroup', "/api/item-types/search")

function renderResults(items) {
  const container = document.querySelector(".results")
  container.innerHTML = ""

  if (!items.length) {
    container.innerHTML = "<p class='muted'>No results</p>"
    return
  }

  for (const item of items) {
    const card = document.createElement("div")
    card.className = "result-card"

    card.innerHTML = `
      <h3>${item.type}</h3>

      <p class="muted">${item.location}</p>

      ${item.instruction ? `<p>${item.instruction}</p>` : ""}

      ${item.battery ? `
        <div class="muted">
          🔋 ${item.battery.voltage}V ·
          ${item.battery.current}A ·
          ${item.battery.capacity}mAh ·
          ${item.battery.charging_type}
        </div>
      ` : ""}

      ${item.tags.length ? `
        <div class="chips">
          ${item.tags.map(t => `<span class="chip">${t}</span>`).join("")}
        </div>
      ` : ""}

      <div class="muted">
        ${item.has_cable ? "🔌 Cable included" : ""}
        ${item.price ? `· €${item.price}` : ""}
      </div>
    `

    container.appendChild(card)
  }
}


const addLocationInput = document.querySelector("#addLocation")
const addParentInput = document.querySelector("#addParent")
const addLocationButton = document.querySelector("#addLocationButton")

addLocationButton.addEventListener("click", async () => {
  const name = addLocationInput.value.trim()
  const parent = addParentInput.value || null

  if (!name) return

  const resp = await fetch("/api/locations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      parent,
    }),
  })

  if (!resp.ok) {
    console.error(await resp.text())
    return
  }

  const data = await resp.json()
  if (resp.status == 200)
  {
  console.log("Location already exists:", data, resp)
  notify("Location already exists", "info")
  }
  if (resp.status == 201)
  {
  console.log("Location created:", data, resp)
  notify("Location Created", "success")
  }
})


locationInput = document.querySelector("#location")
boughtPlace = document.querySelector("#boughtPlace")
price = document.querySelector("#price")
hasDedicatedCable = document.querySelector("#hasDedicatedCable")
acquiredDate = document.querySelector("#acquiredDate")
lastChargeDate = document.querySelector("#lastChargeDate")
lastSeenDate = document.querySelector("#lastSeenDate")
itemGroup = document.querySelector("#itemGroup")
add_item_button = document.querySelector("#addItemButton")


addItemButton.addEventListener("click", async () => {
  const payload = {
    type: itemGroup.value,
    location: locationInput.value,

    last_seen_date: lastSeenDate.value || null,
    last_charge_date: lastChargeDate.value || null,
    acquired_date: acquiredDate.value || null,

    has_dedicated_cable: hasDedicatedCable.checked,
    bought_place: boughtPlace.value || null,
    price: price.value ? Number(price.value) : null,
  }

  const resp = await fetch("/api/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (!resp.ok) {
    teeext = await resp.json()
    console.error(teeext)
    notify(teeext.error, "error")
    return
  }

  const data = await resp.json()
  console.log("Item created:", data)
  notify("Item Created", "success")
})


function getTagsAsList() {
  const chips = document.querySelectorAll("#tags-container .chip")

  return Array.from(chips).map(chip => {
    // Remove the × and trim whitespace
    return chip.childNodes[0].textContent.trim()
  })
}


chargingType = document.querySelector("#chargingType")
capacity = document.querySelector("#capacity")
current = document.querySelector("#current")
voltage = document.querySelector("#voltage")
tags = document.querySelector("#tags")
instructions = document.querySelector("#instructions")
nameInput = document.querySelector("#name")
add_item_group_button = document.querySelector("#addItemGroupButton")


const tabLeft  = document.querySelector("#tab-left")
const tabRight = document.querySelector("#tab-right")
const layout   = document.querySelector(".layout")

tabLeft.addEventListener("click", () => {
  layout.classList.remove("show-right")
  layout.classList.add("show-left")
})

tabRight.addEventListener("click", () => {
  layout.classList.remove("show-left")
  layout.classList.add("show-right")
})

addItemGroupButton.addEventListener("click", async () => {
  const payload = {
    name: nameInput.value.trim(),
    voltage: Number(voltage.value),
    current: Number(current.value),
    capacity: Number(capacity.value),
    charging_type: chargingType.value,
    instruction: instructions.value || null,
    tag_ids: getTagsAsList(), // <-- array you maintain from tag UI
  }

  if (!payload.name) return

  const resp = await fetch("/api/item-types", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })

  if (!resp.ok) {
  	text = await resp.text()
    console.error(text)
    notify(text, "error")
    return
  }

  const data = await resp.json()
  console.log("ItemGroup created:", data)
  notify("Item Group Created", "success")
})


const selectedTags = new Map()
const tagInput = document.getElementById('tag-input')
const tagContainer = document.getElementById('tags-container')

function renderTags() {
  // Remove all existing tag elements except the input
	tagContainer.querySelectorAll('.chip').forEach(chip => chip.remove())

	selectedTags.forEach(tag => {
		const chip = document.createElement('span')
		chip.className = 'chip'
		chip.textContent = tag.name

		const close = document.createElement('span')
		close.textContent = ' ×'
		close.style.cursor = 'pointer'
		close.style.marginLeft = '4px'
		close.onclick = () => {
			selectedTags.delete(tag.id)
			renderTags()
		}

		chip.appendChild(close)
		tagContainer.insertBefore(chip, tagInput)
	})
}

// Handle Enter key to add tag
tagInput.addEventListener('keydown', async (e) => {
	if (e.key === 'Enter') {
		e.preventDefault()
		const name = tagInput.value.trim()
		if (!name) return

			try {
      // Send to backend to create/find tag
				const tag = await fetch('/api/tags', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ name })
				}).then(r => r.json())

				selectedTags.set(tag.id, tag)
				renderTags()
				tagInput.value = ''
			} catch(err) {
				console.error(err)
				notify('Failed to add tag', "error")
			}
		}
	})

let notifyTimeout = null

function notify(message, type = "info", duration = 3000) {
  const banner = document.getElementById("notification")

  banner.textContent = message
  banner.className = `notification show ${type}`
  banner.hidden = false

  clearTimeout(notifyTimeout)

  notifyTimeout = setTimeout(() => {
    banner.classList.remove("show")
    setTimeout(() => {
      banner.hidden = true
    }, 300)
  }, duration)
}
