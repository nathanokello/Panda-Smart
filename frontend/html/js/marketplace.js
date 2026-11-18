document.addEventListener("DOMContentLoaded", async () => {
  const user = await PandaUI.init({
    roles: ["farmer", ...PandaUI.STAFF],
    active: "marketplace"
  });
  const crops = await PandaUI.crops();
  const cropFilter = document.getElementById("listingCropFilter");
  const listingRows = document.getElementById("listingRows");

  cropFilter.innerHTML += PandaUI.options(
    crops,
    (crop) => crop.code,
    (crop) => `${crop.name_en} · ${crop.name_sw}`
  );

  async function loadListings() {
    listingRows.innerHTML = `<p class="muted">Loading listings…</p>`;
    try {
      const listings = await PandaAPI.marketplace({
        crop: cropFilter.value
      });
      listingRows.innerHTML = listings.length
        ? listings.map((listing) => `
          <article class="listing-card">
            <div class="listing-card-head">
              <strong>${PandaUI.cropName(listing.crop)}</strong>
              <span class="badge badge-green">Available</span>
            </div>
            <p><strong>${PandaUI.num(listing.quantity_kg)} kg</strong> at <strong>KES ${PandaUI.num(listing.price_per_kg_kes)}</strong>/kg</p>
            <p class="muted">${PandaUI.esc(listing.description || "No additional description.")}</p>
            <div class="listing-card-foot">
              <span>${PandaUI.esc(listing.farmer_name)}</span>
              <span>${PandaUI.esc(listing.ward)}, ${PandaUI.esc(listing.county)}</span>
            </div>
          </article>
        `).join("")
        : `<p class="muted">No produce listings match this filter.</p>`;
    } catch (error) {
      listingRows.innerHTML = `<p class="notice notice-error">${PandaUI.esc(error.message)}</p>`;
    }
  }

  cropFilter.addEventListener("change", loadListings);
  await loadListings();

  if (user.role !== "farmer") return;

  const panel = document.getElementById("listingFormPanel");
  const cropSelect = document.getElementById("listingCrop");
  const lotSelect = document.getElementById("listingLot");
  const form = document.getElementById("listingForm");
  const message = document.getElementById("listingMessage");

  panel.hidden = false;
  cropSelect.innerHTML = PandaUI.options(
    crops.filter((crop) => crop.storable),
    (crop) => crop.code,
    (crop) => `${crop.name_en} · ${crop.name_sw}`,
    "Select crop"
  );

  try {
    const lots = await PandaAPI.lots({});
    lotSelect.innerHTML =
      `<option value="">No lot selected</option>` +
      lots.map((lot) =>
        `<option value="${PandaUI.esc(lot.id)}">${PandaUI.cropName(lot.crop)} · ${PandaUI.num(lot.summary.latest_weight_kg)} kg</option>`
      ).join("");
  } catch (error) {
    PandaUI.message(message, `Your lots could not be loaded: ${error.message}`);
  }

  form.onsubmit = async (event) => {
    event.preventDefault();
    PandaUI.message(message, "");
    try {
      await PandaUI.busy(form.querySelector("button"), () => PandaAPI.createListing({
        crop: cropSelect.value,
        lot_id: lotSelect.value || null,
        quantity_kg: document.getElementById("listingQuantity").value,
        price_per_kg_kes: document.getElementById("listingPrice").value,
        description: document.getElementById("listingDescription").value.trim()
      }));
      form.reset();
      PandaUI.message(message, "Your produce listing is now live.", "success");
      await loadListings();
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  };
});
