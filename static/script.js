console.log("hello!!!!!!!!!!!!!!!")

const API_BASE = "" // put this for subfolder =>  "/inventory"

let YOSH_ENABLED =
  localStorage.getItem("yosh") !== "false";

let global_param = {"yosh": YOSH_ENABLED}

async function parseApiResponse(resp) {
  const contentType = resp.headers.get("content-type") || ""
  if (contentType.includes("application/json")) {
    try {
      return await resp.json()
    } catch {
      return null
    }
  }

  try {
    const text = await resp.text()
    return text ? { error: text } : null
  } catch {
    return null
  }
}

function getApiErrorMessage(resp, body, fallback = "Request failed") {
  if (body && typeof body === "object" && body.error) return body.error
  if (typeof body === "string" && body.trim()) return body.trim()
  return `${fallback} (${resp.status})`
}

async function deleteItem(id, cardEl) {
  const res = await fetch(`${API_BASE}/api/items?id=${id}`, {
    method: "DELETE",
    headers: {
      "X-Yosh": YOSH_ENABLED,
    }
  })
  const body = await parseApiResponse(res)

  if (!res.ok) {
    notify(getApiErrorMessage(res, body, "Failed to delete item"), "error")
    return
  }

  cardEl.remove()
  notify("Item deleted", "success")
}

let AUTOCOMPLETE_ENABLED =
  localStorage.getItem("autocomplete") !== "false";


const toggleBtn = document.getElementById("toggleAutocomplete");
const searchSection = document.querySelector(".pane.left .search");
function updateToggleUI() {
  if (AUTOCOMPLETE_ENABLED) {
    toggleBtn.textContent = "Search: ON"
    searchSection.style.display = ""
    toggleBtn.style.background = "green"
    toggleBtn.style.borderColor = "green"
  } else {
    toggleBtn.textContent = "Search: OFF"
    searchSection.style.display = "none"
    toggleBtn.style.background = "red"
    toggleBtn.style.borderColor = "red"
  }
}

toggleBtn.addEventListener("click", () => {
  AUTOCOMPLETE_ENABLED = !AUTOCOMPLETE_ENABLED;
  localStorage.setItem("autocomplete", AUTOCOMPLETE_ENABLED);
  updateToggleUI();
});

const tabYosh = document.querySelector("#tab-yosh")

function updateYoshUI() {
  if (YOSH_ENABLED) {
    tabYosh.style.background = "green"
    tabYosh.style.borderColor = "green"
  } else {
    tabYosh.style.background = "red"
    tabYosh.style.borderColor = "red"
  }
}
updateYoshUI();
updateToggleUI();

tabYosh.addEventListener("click", () => {
  YOSH_ENABLED = !YOSH_ENABLED;
  localStorage.setItem("yosh", YOSH_ENABLED);
  updateYoshUI();
})


const advBtn = document.getElementById("advancedSearchBtn");
const advPanel = document.querySelector(".filters");

async function handleAutocompleteSelect({ input, item }) {
  if (!AUTOCOMPLETE_ENABLED) return;

  // Default behavior (search / fill field)
  input.value = item.label
  input.dataset.id = item.id

  // Special-case: Location ID input should store the numeric ID (not the breadcrumb label).
  if (input.id === "locationID") {
    input.value = item.id ?? ""
    input.dataset.id = item.id
    return
  }

  // TAG INPUT = ADD TAG IMMEDIATELY
  if (input.id === "tag-input") {
    selectedTags.add(item.label)
    renderTags()
    input.value = ""
    // notify(`Tag "${item.label}" added`, "success", 1500)
  }


  let url = null

  switch (input.id) {
    case "tag-search":
    case "tag-input":
      url = `/api/items/tag?q=${encodeURIComponent(item.label)}`
      break

    case "location":
    case "addLocation":
    case "addParent":
    case "location-search":
      url = `/api/items/location?q=${encodeURIComponent(item.label)}`
      break

    case "itemGroup":
    case "name":
      url = `/api/items/group?q=${encodeURIComponent(item.label)}`
      break

    case "voltage":
      url = `/api/items/voltage?q=${encodeURIComponent(item.label)}`
      break

    case "current":
      url = `/api/items/current?q=${encodeURIComponent(item.label)}`
      break

    case "capacity":
      url = `/api/items/capacity?q=${encodeURIComponent(item.label)}`
      break

    case "chargingType":
      url = `/api/items/charging-type?q=${encodeURIComponent(item.label)}`
      break

    case "boughtPlace":
      url = `/api/items/bought-place?q=${encodeURIComponent(item.label)}`
      break

    case "price":
      url = `/api/items/price?q=${encodeURIComponent(item.label)}`
      break

    case "lastSeenDate":
      url = `/api/items/last-seen?q=${encodeURIComponent(item.label)}`
      break

    case "lastUseDate":
      url = `/api/items/last-use?q=${encodeURIComponent(item.label)}`
      break

    case "acquiredDate":
      url = `/api/items/acquired?q=${encodeURIComponent(item.label)}`
      break

    case "itemID":
      url = `/api/items/by-id?q=${encodeURIComponent(item.id)}`
      break
    case "color":
      url = `/api/items/color?q=${encodeURIComponent(item.id)}`
      break
    case "variant":
      url = `/api/items/variant?q=${encodeURIComponent(item.id)}`
      break
    case "status":
      url = `/api/items/status?q=${encodeURIComponent(item.id)}`
      break
  }

  if (url) {
    const res = await fetch(API_BASE + url, {
      headers: {
      "X-Yosh": YOSH_ENABLED,
    }
    })
    const data = await parseApiResponse(res)
    if (!res.ok) {
      notify(getApiErrorMessage(res, data, "Search failed"), "error")
      return
    }
    renderResults(data)
  }
}


function autoComplete({ selector, api, onSelect }) {
  const inputs = document.querySelectorAll(selector)

  inputs.forEach(input => {
    const list = input.nextElementSibling
    let items = []
    let activeIndex = -1

    function close() {
      list.hidden = true
      list.innerHTML = ""
      activeIndex = -1
    }

    function render(results) {
      items = results
      list.innerHTML = ""

      if (!results.length) return close()

      results.forEach((item, i) => {
        const li = document.createElement("li")
        li.textContent = item.label

        li.addEventListener("mousedown", e => {
          e.preventDefault()
          selectItem(i)
        })

        list.appendChild(li)
      })

      list.hidden = false
    }

    function highlight() {
      [...list.children].forEach((li, i) => {
        li.classList.toggle("active", i === activeIndex)
      })
    }

    async function selectItem(index) {
      const item = items[index]
      console.log("selectItem", index, item)
      if (!item) return

      input.value = item.label
      input.dataset.id = item.id
      close()

      // delegate behavior based on input.id
      if (onSelect) {
        await onSelect({
          input,
          item
        })
      }
    }

    input.addEventListener("input", async e => {
      if (!AUTOCOMPLETE_ENABLED) return;
      const q = e.target.value.trim()
      if (!q) return close()

      const limitEl = document.getElementById("limitNumber")
      let limitNumber = parseInt(limitEl?.value, 10)
      if (!Number.isFinite(limitNumber) || limitNumber <= 0) limitNumber = 10

      const res = await fetch(`${API_BASE}${api}?&autocomplete=true&q=${encodeURIComponent(q)}&limitNumber=${limitNumber}`,
      {
        headers: {
      "X-Yosh": YOSH_ENABLED,
    }
      })
      const data = await parseApiResponse(res)
      if (!res.ok) {
        notify(getApiErrorMessage(res, data, "Autocomplete failed"), "error", 1500)
        close()
        return
      }
      render(Array.isArray(data) ? data : [])
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
            await selectItem(activeIndex)
          }
          break
        case "Escape":
          close()
          break
      }
    })

    document.addEventListener("mousedown", e => {
      if (!input.contains(e.target) && !list.contains(e.target)) {
        close()
      }
    })
  })
}

autoComplete({ selector: ".location", api: "/api/items/location", onSelect: handleAutocompleteSelect })
autoComplete({ selector: ".tag", api: "/api/items/tag", onSelect: handleAutocompleteSelect })
autoComplete({ selector: ".itemGroup", api: "/api/items/group", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#voltage", api: "/api/items/voltage", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#current", api: "/api/items/current", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#capacity", api: "/api/items/capacity", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#chargingType", api: "/api/items/charging-type", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#boughtPlace", api: "/api/items/bought-place", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#price", api: "/api/items/price", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#lastSeenDate", api: "/api/items/last-seen", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#lastUseDate", api: "/api/items/last-use", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#acquiredDate", api: "/api/items/acquired", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#color", api: "/api/items/color", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#variant", api: "/api/items/variant", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#status", api: "/api/items/status", onSelect: handleAutocompleteSelect })
autoComplete({ selector: "#itemID", api: "/api/items/id", onSelect: handleAutocompleteSelect })

function isoLabel(label, value) {
  return value ? `<div class="muted"><strong>${label}:</strong> ${value}</div>` : ""
}

function boolLabel(label, value) {
  return value ? `<div class="muted">${label}</div>` : ""
}

function renderBattery(b) {
  if (!b) return ""

  const parts = []
  if (b.voltage) parts.push(`${b.voltage}V`)
  if (b.current) parts.push(`${b.current}A`)
  if (b.capacity) parts.push(`${b.capacity}mAh`)
  if (b.charging_type) parts.push(b.charging_type)

  return parts.length
    ? `<div class="muted">🔋 ${parts.join(" · ")}</div>`
    : ""
}


function loadItemGroup(group) {
  nameInput.value = group.group
  instructions.value = group.instruction || ""

  // Battery
  voltage.value = group.battery?.voltage || ""
  current.value = group.battery?.current || ""
  capacity.value = group.battery?.capacity || ""
  chargingType.value = group.battery?.charging_type || ""

  // Tags
  selectedTags.clear()
  group.tags.forEach(t => selectedTags.add(t))
  renderTags()
}
function loadItem(item) {
  itemID.value = item.id
  itemGroup.value = item.group
  locationInput.value = item.location

  lastSeenDate.value = item.last_seen || ""
  lastUseDate.value = item.last_use || ""
  acquiredDate.value = item.acquired || ""

  hasDedicatedCable.checked = !!item.has_cable
  boughtPlace.value = item.bought_place || ""
  price.value = item.price ?? ""
  variant.value = item.variant || ""
  color.value = item.color || ""
  statusID.value = item.status || ""
}

function loadLocation(item) {
  locationID.value = item.location_id || ""
  addLocationInput.value = item.location
  addParentInput.value = item.location_parent || ""
  loadFurnitureMaps()
}

function loadItemForEdit(item) {
  loadItemGroup(item)
  loadItem(item)
  loadLocation(item)

  // Switch to edit pane
  layout.classList.remove("show-right")
  layout.classList.add("show-left")

  notify("Editing item", "info")
}

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
      <div class="card-header">
        <h3>${item.group}</h3>
        <div class="actions">
          <button class="edit-btn">✏️</button>
          <button class="danger-btn">🗑</button>
        </div>
      </div>

      ${item.instruction ? `<p>${item.instruction}</p>` : ""}

      <div class="stack-sm">
        ${renderBattery(item.battery)}

        ${item.tags?.length ? `
          <div class="chips">
            ${item.tags.map(t => `<span class="chip">${t}</span>`).join("")}
          </div>
        ` : ""}

        ${isoLabel("Location", item.location)}
        ${isoLabel("Color", item.color)}
        ${isoLabel("Variant", item.variant)}
        ${isoLabel("Bought at", item.bought_place)}
        ${isoLabel("Price", item.price ? `€${item.price}` : null)}
        ${isoLabel("Last seen", item.last_seen)}
        ${isoLabel("Acquired", item.acquired)}
        ${isoLabel("Last used", item.last_use)}
        ${boolLabel("🔌 Dedicated cable included", item.has_cable)}
        ${isoLabel("Status", item.status)}
      </div>
    `

    card.querySelector(".danger-btn").onclick =
      () => deleteItem(item.id, card)

    card.querySelector(".edit-btn").onclick =
      () => loadItemForEdit(item)

    const jamyBtn = document.createElement("button")
    jamyBtn.type = "button"
    jamyBtn.className = "jamy-btn"
    jamyBtn.textContent = "ici jamy!!!!"
    jamyBtn.onclick = () => openFinder(item.location_id, item.location)
    card.appendChild(jamyBtn)

    container.appendChild(card)
  }
}




const addLocationInput = document.querySelector("#addLocation")
const addParentInput = document.querySelector("#addParent")
const locationID = document.querySelector("#locationID")
const addLocationButton = document.querySelector("#addLocationButton")

addLocationButton.addEventListener("click", async () => {
  const name = addLocationInput.value.trim()
  const parent = addParentInput.value.trim() || null
  const locID = locationID.value.trim()

  if (!name) return
  if (locID == "") {
    const resp = await fetch(`${API_BASE}/api/locations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Yosh": YOSH_ENABLED,
      },
      body: JSON.stringify({
        name,
        parent,
      }),
    })
    const body = await parseApiResponse(resp)
    if (!resp.ok) {
      console.error(body)
      notify(getApiErrorMessage(resp, body, "Failed to save location"), "error")
      return
    }
    const data = body || {}
    if (resp.status == 200) {
      console.log("Location already exists:", data, resp)
      notify("Location already exists", "info")
    }
    if (resp.status == 201) {
      console.log("Location created:", data, resp)
      notify("Location Created", "success")
    }
    if (resp.status == 202) {
      console.log("Location updated:", data, resp)
      notify("Location updated", "success")
    }
    return
  }
  const resp = await fetch(`${API_BASE}/api/locations/${locID}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Yosh": YOSH_ENABLED,
      },
      body: JSON.stringify({
        name,
        parent,
      }),
    })
    const body = await parseApiResponse(resp)

    if (!resp.ok) {
      console.error(body)
      notify(getApiErrorMessage(resp, body, "Failed to rename location"), "error")
      return
    }
    const data = body || {}
    if (resp.status == 200) {
      console.log("Location created:", data, resp)
      notify("Location Renamed", "success")
    }
})


locationInput = document.querySelector("#location")
boughtPlace = document.querySelector("#boughtPlace")
price = document.querySelector("#price")
hasDedicatedCable = document.querySelector("#hasDedicatedCable")
acquiredDate = document.querySelector("#acquiredDate")
lastUseDate = document.querySelector("#lastUseDate")
lastSeenDate = document.querySelector("#lastSeenDate")
itemGroup = document.querySelector("#itemGroup")
itemID = document.querySelector("#itemID")
add_item_button = document.querySelector("#addItemButton")
color = document.querySelector("#color")
variant = document.querySelector("#variant")
statusID = document.querySelector("#status")

addItemButton.addEventListener("click", async () => {
  const payload = {
    id: itemID.value || null,
    group: itemGroup.value,
    location: locationInput.value,

    last_seen_date: lastSeenDate.value || null,
    last_use_date: lastUseDate.value || null,
    acquired_date: acquiredDate.value || null,
    has_dedicated_cable: Boolean(hasDedicatedCable.value),
    bought_place: boughtPlace.value || null,
    price: price.value ? Number(price.value) : null,
    color: color.value || null,
    variant: variant.value || null,
    status: statusID.value || null,
  }

  const resp = await fetch(`${API_BASE}/api/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json",
      "X-Yosh": YOSH_ENABLED,
    },
    body: JSON.stringify(payload),
  })
  const body = await parseApiResponse(resp)

  if (!resp.ok) {
    console.error(body)
    notify(getApiErrorMessage(resp, body, "Failed to save item"), "error")
    return
  }

  const data = body || {}
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


const tabLeft = document.querySelector("#tab-left")
const tabRight = document.querySelector("#tab-right")
const layout = document.querySelector(".layout")
const desktopLayoutQuery = window.matchMedia("(min-width: 1201px)")

function setSplitView(split) {
  // Split 1: Edit only (left)
  // Split 2: Edit + View (left + right)
  // Split 3: Edit + View + Filters (left + right + filters)
  layout.classList.remove("show-left", "show-right", "show-filters")
  if (split === 1) {
    layout.classList.add("show-left")
  } else if (split === 2) {
    layout.classList.add("show-left", "show-right")
  } else if (split === 3) {
    layout.classList.add("show-left", "show-right", "show-filters")
  }
}

function isDesktopLayout() {
  return desktopLayoutQuery.matches
}

function setPanelButtonState(button, isActive) {
  if (!button) return
  button.classList.toggle("panel-active", !!isActive)
}

function refreshDesktopPanelButtonStates() {
  setPanelButtonState(tabLeft, !layout.classList.contains("hide-left"))
  setPanelButtonState(tabRight, !layout.classList.contains("hide-right"))
  setPanelButtonState(advBtn, !layout.classList.contains("hide-filters"))
}

function toggleDesktopPanel(panelName) {
  const className = `hide-${panelName}`
  layout.classList.toggle(className)
  refreshDesktopPanelButtonStates()
}

function isTypingInControl(el) {
  if (!el) return false
  const tag = (el.tagName || "").toLowerCase()
  if (tag === "input" || tag === "textarea" || tag === "select") return true
  return !!el.isContentEditable
}

document.addEventListener("keydown", e => {
  // Don't steal keybinds while typing.
  if (isTypingInControl(document.activeElement)) return
  if (e.altKey || e.ctrlKey || e.metaKey) return

  if (e.key === "1") {
    e.preventDefault()
    setSplitView(1)
  } else if (e.key === "2") {
    e.preventDefault()
    setSplitView(2)
  } else if (e.key === "3") {
    e.preventDefault()
    setSplitView(3)
  } else if (e.key === "ArrowLeft") {
    e.preventDefault()
    setSplitView(1)
  } else if (e.key === "ArrowRight") {
    e.preventDefault()
    setSplitView(2)
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    setSplitView(3)
  }
})

advBtn.addEventListener("click", () => {
  if (isDesktopLayout()) {
    toggleDesktopPanel("filters")
    return
  }
  layout.classList.remove("show-right")
  layout.classList.remove("show-left")
  layout.classList.add("show-filters")
})


tabLeft.addEventListener("click", () => {
  if (isDesktopLayout()) {
    toggleDesktopPanel("left")
    return
  }
  layout.classList.remove("show-right")
  layout.classList.remove("show-filters")
  layout.classList.add("show-left")
})

tabRight.addEventListener("click", () => {
  if (isDesktopLayout()) {
    toggleDesktopPanel("right")
    return
  }
  layout.classList.remove("show-filters")
  layout.classList.remove("show-left")
  layout.classList.add("show-right")
})

desktopLayoutQuery.addEventListener("change", () => {
  refreshDesktopPanelButtonStates()
})
refreshDesktopPanelButtonStates()

addItemGroupButton.addEventListener("click", async () => {
  const payload = {
    id: null,
    name: nameInput.value.trim(),
    voltage: Number(voltage.value),
    current: Number(current.value),
    capacity: Number(capacity.value),
    charging_type: chargingType.value,
    instruction: instructions.value || null,
    tags: getTagsAsList(), // <-- array you maintain from tag UI
  }

  if (!payload.name) return

  const resp = await fetch(`${API_BASE}/api/item-group`, {
    method: "POST",
    headers: { "Content-Type": "application/json",
      "X-Yosh": YOSH_ENABLED,
     },
    body: JSON.stringify(payload),
  })
  const body = await parseApiResponse(resp)

  if (!resp.ok) {
    console.error(body)
    notify(getApiErrorMessage(resp, body, "Failed to save item group"), "error")
    return
  }

  const data = body || {}
  console.log("ItemGroup created:", data)
  notify("Item Group Created", "success")
})


const selectedTags = new Set()
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
function renderTags() {
  tagContainer.querySelectorAll('.chip').forEach(chip => chip.remove())

  selectedTags.forEach(tag => {
    const chip = document.createElement('span')
    chip.className = 'chip'
    chip.textContent = tag

    const close = document.createElement('span')
    close.textContent = ' ×'
    close.style.cursor = 'pointer'
    close.style.marginLeft = '4px'

    close.onclick = () => {
      selectedTags.delete(tag)
      renderTags()
    }

    chip.appendChild(close)
    tagContainer.insertBefore(chip, tagInput)
  })
}



// Handle Enter key to add tag
tagInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault()

    const name = tagInput.value.trim()
    if (!name) return

    selectedTags.add(name)   // ← add(), not set()
    renderTags()
    tagInput.value = ''
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

document.getElementById("runAdvancedSearch").addEventListener("click", async () => {
  const params = new URLSearchParams();

  if (priceMin.value) params.set("price_min", priceMin.value);
  if (priceMax.value) params.set("price_max", priceMax.value);
  if (dateAfter.value) params.set("after", dateAfter.value);
  if (dateBefore.value) params.set("before", dateBefore.value);
  if (tagPartial.value) params.set("tag_partial", tagPartial.value);

  const res = await fetch(`${API_BASE}/api/items?${params.toString()}`, {
    headers: {
      "X-Yosh": YOSH_ENABLED,
    }
  });
  const data = await parseApiResponse(res);
  if (!res.ok) {
    notify(getApiErrorMessage(res, data, "Advanced search failed"), "error")
    return
  }
  renderResults(data);
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]))
}

const finderModal = document.getElementById("finder-modal")
const finderMaps = document.getElementById("finder-maps")
const finderEmpty = document.getElementById("finder-empty")
const finderTitle = document.getElementById("finder-title")
const tabFinder = document.getElementById("tab-finder")

function closeFinder() {
  finderModal.hidden = true
}

async function openFinder(locationId, label) {
  finderTitle.textContent = label ? `Ici jamy!!!! — ${label}` : "Ici jamy!!!!"
  finderModal.hidden = false
  finderMaps.innerHTML = ""
  finderEmpty.hidden = true
  const url = locationId
    ? `${API_BASE}/api/finder?location_id=${encodeURIComponent(locationId)}`
    : `${API_BASE}/api/finder`
  const res = await fetch(url, {
    headers: { "X-Yosh": YOSH_ENABLED },
  })
  const data = await parseApiResponse(res)
  if (!res.ok) {
    notify(getApiErrorMessage(res, data, "Could not load furniture photos"), "error")
    return
  }
  renderFinder(data?.maps || [])
}

function renderFinder(maps) {
  finderMaps.innerHTML = ""
  if (!maps.length) {
    finderEmpty.hidden = false
    return
  }
  finderEmpty.hidden = true
  for (const m of maps) {
    const pile = document.createElement("div")
    pile.className = "finder-pile" + (m.highlight ? " has-hit" : "")
    const hi = m.highlight
    const placeBelow = hi && hi.y < 18
    pile.innerHTML = `
      <h3>${escapeHtml(m.name)}${m.location ? ` <span class="muted">· ${escapeHtml(m.location)}</span>` : ""}</h3>
      <div class="finder-stage">
        <img src="${API_BASE}${m.photo_url}" alt="${escapeHtml(m.name)}">
        ${hi ? `
          <div class="jamy-hit" style="left:${hi.x}%;top:${hi.y}%;width:${hi.w}%;height:${hi.h}%;">
            <div class="jamy-callout ${placeBelow ? "below" : "above"}">ici jamy!!!!</div>
          </div>` : ""}
      </div>
    `
    finderMaps.appendChild(pile)
  }
}

document.getElementById("finder-close").addEventListener("click", closeFinder)
finderModal.addEventListener("click", e => {
  if (e.target === finderModal) closeFinder()
})
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !finderModal.hidden) closeFinder()
})
tabFinder.addEventListener("click", () => openFinder())

async function loadFurnitureMaps() {
  const list = document.getElementById("furnitureMapsList")
  const locID = locationID.value.trim()
  if (!list) return
  if (!locID) {
    list.innerHTML = "<p class='muted'>Load a location ID to attach photos to this furniture.</p>"
    return
  }
  const res = await fetch(`${API_BASE}/api/furniture-maps?location_id=${encodeURIComponent(locID)}`, {
    headers: { "X-Yosh": YOSH_ENABLED },
  })
  const maps = await parseApiResponse(res)
  if (!res.ok) {
    notify(getApiErrorMessage(res, maps, "Could not load furniture photos"), "error")
    return
  }
  renderFurnitureAdmin(Array.isArray(maps) ? maps : [])
}

function renderFurnitureAdmin(maps) {
  const list = document.getElementById("furnitureMapsList")
  list.innerHTML = ""
  if (!maps.length) {
    list.innerHTML = "<p class='muted'>No photos on this location yet. Upload Kallax / drawers here.</p>"
    return
  }
  for (const m of maps) {
    const card = document.createElement("div")
    card.className = "furniture-map-card"
    const zonesHtml = (m.zones || []).map(z => `
      <div class="furniture-zone-row" data-zone-id="${z.id}">
        <span class="slot-swatch" style="background:${escapeHtml(z.color)}" title="${escapeHtml(z.color)} slot ${z.slot}"></span>
        <input value="${escapeHtml(z.location || "")}" placeholder="Location for slot ${z.slot} (${escapeHtml(z.color)})" />
        <button type="button" class="zone-save">Link</button>
      </div>
    `).join("")
    card.innerHTML = `
      <strong>${escapeHtml(m.name)}</strong>
      <img src="${API_BASE}${m.photo_url}" alt="">
      <label>Add / replace color mask</label>
      <input type="file" class="mask-file" accept="image/png,image/*">
      ${zonesHtml || "<p class='muted'>Upload a color mask to generate the boxes.</p>"}
      <button type="button" class="delete-map">Delete photo</button>
    `

    card.querySelector(".delete-map").onclick = async () => {
      const res = await fetch(`${API_BASE}/api/furniture-maps/${m.id}`, {
        method: "DELETE",
        headers: { "X-Yosh": YOSH_ENABLED },
      })
      const body = await parseApiResponse(res)
      if (!res.ok) {
        notify(getApiErrorMessage(res, body, "Failed to delete photo"), "error")
        return
      }
      notify("Furniture photo deleted", "success")
      loadFurnitureMaps()
    }

    const maskInput = card.querySelector(".mask-file")
    maskInput.addEventListener("change", async () => {
      if (!maskInput.files[0]) return
      const fd = new FormData()
      fd.append("mask", maskInput.files[0])
      const res = await fetch(`${API_BASE}/api/furniture-maps/${m.id}/mask`, {
        method: "POST",
        headers: { "X-Yosh": YOSH_ENABLED },
        body: fd,
      })
      const body = await parseApiResponse(res)
      if (!res.ok) {
        notify(getApiErrorMessage(res, body, "Failed to read mask"), "error")
        return
      }
      notify(`Mask imported (${body?.zones ?? 0} boxes)`, "success")
      loadFurnitureMaps()
    })

    card.querySelectorAll(".zone-save").forEach(btn => {
      btn.addEventListener("click", async () => {
        const row = btn.closest(".furniture-zone-row")
        const zoneId = row.dataset.zoneId
        const locValue = row.querySelector("input").value.trim()
        const res = await fetch(`${API_BASE}/api/furniture-zones/${zoneId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-Yosh": YOSH_ENABLED,
          },
          body: JSON.stringify({ location: locValue }),
        })
        const body = await parseApiResponse(res)
        if (!res.ok) {
          notify(getApiErrorMessage(res, body, "Failed to link zone"), "error")
          return
        }
        notify("Zone linked", "success")
        loadFurnitureMaps()
      })
    })

    list.appendChild(card)
  }
}

document.getElementById("uploadFurnitureMapButton").addEventListener("click", async () => {
  const name = document.getElementById("furnitureMapName").value.trim()
  const photo = document.getElementById("furniturePhoto").files[0]
  const mask = document.getElementById("furnitureMask").files[0]
  const locID = locationID.value.trim()
  const locationName = addLocationInput.value.trim()

  if (!name || !photo) {
    notify("Name and furniture photo are required", "error")
    return
  }

  const fd = new FormData()
  fd.append("name", name)
  fd.append("photo", photo)
  if (mask) fd.append("mask", mask)
  if (locID) fd.append("location_id", locID)
  if (locationName) fd.append("location", locationName)

  const res = await fetch(`${API_BASE}/api/furniture-maps`, {
    method: "POST",
    headers: { "X-Yosh": YOSH_ENABLED },
    body: fd,
  })
  const body = await parseApiResponse(res)
  if (!res.ok) {
    notify(getApiErrorMessage(res, body, "Failed to upload furniture photo"), "error")
    return
  }
  notify(`Furniture photo uploaded${body?.zones ? ` (${body.zones} boxes)` : ""}`, "success")
  document.getElementById("furniturePhoto").value = ""
  document.getElementById("furnitureMask").value = ""
  loadFurnitureMaps()
})
