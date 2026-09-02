(() => {
  const API = "/api/inventory/";

  const $ = (selector) => document.querySelector(selector);

  const list = (data) =>
    Array.isArray(data) ? data : (data?.results || []);

  const esc = (value) =>
    String(value ?? "—").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[char]);

  const money = (value) =>
    new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(Number(value || 0));

  const csrf = () =>
    decodeURIComponent(
      document.cookie
        .split("; ")
        .find((cookie) => cookie.startsWith("csrftoken="))
        ?.split("=")[1] || ""
    );

  let stocks = [];
  let materials = [];
  let warehouses = [];
  let categories = [];
  let currentUser = null;


  // ------------------------------------------------------------
  // API REQUEST
  // ------------------------------------------------------------

  async function request(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: {
        Accept: "application/json",

        ...(options.method
          ? {
              "Content-Type": "application/json",
              "X-CSRFToken": csrf(),
            }
          : {}),

        ...options.headers,
      },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data.detail ||
        Object.values(data)
          .flat()
          .join(" ") ||
        `Request failed (${response.status})`
      );
    }

    return data;
  }


  // ------------------------------------------------------------
  // DROPDOWN OPTIONS
  // ------------------------------------------------------------

  const opts = (
    items,
    value,
    text,
    placeholder
  ) =>
    `<option value="">${placeholder}</option>` +
    items
      .map(
        (item) =>
          `<option value="${esc(item.id)}" ${
            item.id === value ? "selected" : ""
          }>${esc(text(item))}</option>`
      )
      .join("");


  // ------------------------------------------------------------
  // INVENTORY TABLE
  // ------------------------------------------------------------

  function render() {
    const searchInput = $("[data-inventory-search]");
    const warehouseSelect = $("[data-inventory-warehouse]");
    const stockSelect = $("[data-inventory-stock]");
    const rowsContainer = $("[data-inventory-rows]");

    const query = searchInput
      ? searchInput.value.trim().toLowerCase()
      : "";

    const warehouse = warehouseSelect
      ? warehouseSelect.value
      : "";

    const stockFilter = stockSelect
      ? stockSelect.value
      : "";

    const rows = stocks.filter((stock) => {
      const matchesWarehouse =
        !warehouse || stock.warehouse === warehouse;

      const matchesStock =
        !stockFilter ||
        (
          stockFilter === "low"
            ? stock.is_low_stock
            : !stock.is_low_stock
        );

      const searchableText = [
        stock.material_name,
        stock.material_sku,
        stock.warehouse_name,
      ]
        .join(" ")
        .toLowerCase();

      const matchesSearch =
        !query || searchableText.includes(query);

      return (
        matchesWarehouse &&
        matchesStock &&
        matchesSearch
      );
    });


    // ----------------------------------------------------------
    // TABLE
    // ----------------------------------------------------------

    if (!rows.length) {
      rowsContainer.innerHTML = `
        <tr>
          <td colspan="8">
            <strong>No stock balances found.</strong>
          </td>
        </tr>
      `;
    } else {
      rowsContainer.innerHTML = rows
        .map((stock) => {
          const material = materials.find(
            (item) => item.id === stock.material
          );

          const unitCost = Number(
            material?.standard_cost || 0
          );

          const statusClass = stock.is_low_stock
            ? "at-risk"
            : "active";

          const statusText = stock.is_low_stock
            ? "Low stock"
            : "In stock";

          return `
            <tr>

              <td>
                <strong>${esc(stock.material_name)}</strong>
                <span>View details</span>
              </td>

              <td>
                ${esc(stock.material_sku)}
              </td>

              <td>
                ${esc(stock.warehouse_name)}
              </td>

              <td>
                ${esc(stock.quantity)}
              </td>

              <td>
                —
              </td>

              <td>
                ${esc(stock.minimum_stock_level)}
              </td>

              <td>
                <span class="status ${statusClass}">
                  <i></i>
                  ${statusText}
                </span>
              </td>

              <td>
                <button
                  class="quiet-button"
                  type="button"
                  data-movement-material="${esc(stock.material)}"
                  data-movement-warehouse="${esc(stock.warehouse)}"
                >
                  Record
                </button>
              </td>

            </tr>
          `;
        })
        .join("");
    }


    // ----------------------------------------------------------
    // DASHBOARD METRICS
    // ----------------------------------------------------------

    const itemsMetric =
      $("[data-inventory-metric=items]");

    const lowMetric =
      $("[data-inventory-metric=low]");

    const valueMetric =
      $("[data-inventory-metric=value]");

    const transfersMetric =
      $("[data-inventory-metric=transfers]");

    if (itemsMetric) {
      itemsMetric.textContent = stocks.length;
    }

    if (lowMetric) {
      lowMetric.textContent =
        stocks.filter((stock) => stock.is_low_stock).length;
    }

    if (valueMetric) {
      const inventoryValue = stocks.reduce(
        (total, stock) => {
          const material = materials.find(
            (item) => item.id === stock.material
          );

          const cost = Number(
            material?.standard_cost || 0
          );

          return (
            total +
            Number(stock.quantity || 0) * cost
          );
        },
        0
      );

      valueMetric.textContent = money(inventoryValue);
    }

    // transfers metric is updated by load()
  }


  // ------------------------------------------------------------
  // LOAD INVENTORY DATA
  // ------------------------------------------------------------

  async function loadInventory() {
    const [stockData, movementData] =
      await Promise.all([
        request(`${API}stocks/?page_size=100`),
        request(`${API}stock-movements/?page_size=100`),
      ]);

    stocks = list(stockData);

    const movements = list(movementData);

    const today = new Date()
      .toISOString()
      .slice(0, 10);

    const transfersToday = movements.filter(
      (movement) =>
        movement.movement_type === "TRANSFER" &&
        movement.movement_date?.startsWith(today)
    ).length;

    const transfersMetric =
      $("[data-inventory-metric=transfers]");

    if (transfersMetric) {
      transfersMetric.textContent = transfersToday;
    }

    render();
  }


  // ------------------------------------------------------------
  // CURRENT USER
  // ------------------------------------------------------------
  //
  // IMPORTANT:
  // This request is intentionally separate from the initial
  // inventory loading.
  //
  // /api/auth/me/ currently returns 500 because UserSerializer
  // expects a "role" attribute that your User model does not have.
  //
  // Inventory should still load without it.
  // ------------------------------------------------------------

  async function loadCurrentUser() {
    try {
      currentUser = await request("/api/auth/me/");
      return currentUser;
    } catch (error) {
      console.warn(
        "Could not load current user:",
        error.message
      );

      currentUser = null;
      return null;
    }
  }


  // ------------------------------------------------------------
  // DIALOG
  // ------------------------------------------------------------

  function openDialog(kind, preset = {}) {
    const dialog = $("[data-inventory-dialog]");
    const fields = $("[data-inventory-fields]");

    dialog.dataset.kind = kind;

    $("[data-inventory-error]").textContent = "";


    // ----------------------------------------------------------
    // MATERIAL
    // ----------------------------------------------------------

    if (kind === "material") {
      $("[data-inventory-title]").textContent =
        "Add material";

      $("[data-inventory-submit]").textContent =
        "Create material";

      fields.innerHTML = `
        <label>
          Material name
          <input
            name="name"
            required
          >
        </label>

        <label>
          SKU
          <input
            name="sku"
            required
          >
        </label>

        <label>
          Category
          <select
            name="category"
            required
          >
            ${opts(
              categories,
              "",
              (item) => item.name,
              "Select category"
            )}
          </select>
        </label>

        <label>
          Unit
          <input
            name="unit"
            placeholder="e.g. bag, kg, m"
            required
          >
        </label>

        <label>
          Standard cost
          <input
            name="standard_cost"
            type="number"
            min="0"
            step="0.01"
          >
        </label>

        <label>
          Minimum stock
          <input
            name="minimum_stock_level"
            type="number"
            min="0"
            step="0.001"
            value="0"
          >
        </label>

        <label style="grid-column:1/-1">
          Description
          <textarea name="description"></textarea>
        </label>
      `;
    }


    // ----------------------------------------------------------
    // WAREHOUSE
    // ----------------------------------------------------------

    else if (kind === "warehouse") {
      $("[data-inventory-title]").textContent =
        "New warehouse";

      $("[data-inventory-submit]").textContent =
        "Create warehouse";

      fields.innerHTML = `
        <label>
          Warehouse name
          <input
            name="name"
            required
          >
        </label>

        <label>
          Location
          <input
            name="location"
          >
        </label>
      `;
    }


    // ----------------------------------------------------------
    // CATEGORY
    // ----------------------------------------------------------

    else if (kind === "category") {
      $("[data-inventory-title]").textContent =
        "New material category";

      $("[data-inventory-submit]").textContent =
        "Create category";

      fields.innerHTML = `
        <label>
          Category name
          <input
            name="name"
            required
          >
        </label>

        <label>
          Description
          <input
            name="description"
          >
        </label>
      `;
    }


    // ----------------------------------------------------------
    // STOCK MOVEMENT
    // ----------------------------------------------------------

    else {
      $("[data-inventory-title]").textContent =
        "Record stock movement";

      $("[data-inventory-submit]").textContent =
        "Record movement";

      fields.innerHTML = `
        <label>
          Movement type

          <select
            name="movement_type"
            data-movement-type
          >
            <option value="IN">
              Stock in
            </option>

            <option value="OUT">
              Stock out
            </option>

            <option value="RETURN">
              Return
            </option>

            <option value="ADJUSTMENT">
              Adjustment
            </option>

            <option value="TRANSFER">
              Transfer between stores
            </option>
          </select>
        </label>


        <label>
          Material

          <select
            name="material"
            required
          >
            ${opts(
              materials,
              preset.material,
              (item) =>
                `${item.sku} — ${item.name}`,
              "Select material"
            )}
          </select>
        </label>


        <label data-source>
          Warehouse

          <select
            name="warehouse"
            required
          >
            ${opts(
              warehouses,
              preset.warehouse,
              (item) => item.name,
              "Select warehouse"
            )}
          </select>
        </label>


        <label
          data-transfer
          hidden
        >
          From warehouse

          <select name="from_warehouse">
            ${opts(
              warehouses,
              preset.warehouse,
              (item) => item.name,
              "Select source"
            )}
          </select>
        </label>


        <label
          data-transfer
          hidden
        >
          To warehouse

          <select name="to_warehouse">
            ${opts(
              warehouses,
              "",
              (item) => item.name,
              "Select destination"
            )}
          </select>
        </label>


        <label>
          Quantity

          <input
            name="quantity"
            type="number"
            step="0.001"
            min="0.001"
            required
          >
        </label>


        <label>
          Reference

          <input
            name="reference"
          >
        </label>


        <label style="grid-column:1/-1">
          Notes

          <textarea
            name="notes"
          ></textarea>
        </label>
      `;


      const movementType =
        fields.querySelector(
          "[data-movement-type]"
        );

      movementType.addEventListener(
        "change",
        (event) => {
          const transfer =
            event.target.value === "TRANSFER";

          const source =
            fields.querySelector(
              "[data-source]"
            );

          const warehouse =
            fields.querySelector(
              "[name=warehouse]"
            );

          const transferFields =
            fields.querySelectorAll(
              "[data-transfer]"
            );

          source.hidden = transfer;

          transferFields.forEach(
            (field) => {
              field.hidden = !transfer;
            }
          );

          warehouse.required = !transfer;

          fields
            .querySelectorAll(
              "[name=from_warehouse],[name=to_warehouse]"
            )
            .forEach((field) => {
              field.required = transfer;
            });
        }
      );
    }

    dialog.showModal();
  }


  // ------------------------------------------------------------
  // CREATE / SAVE
  // ------------------------------------------------------------

  async function submitForm(event) {
    event.preventDefault();

    const form = event.currentTarget;

    const dialog =
      $("[data-inventory-dialog]");

    const kind =
      dialog.dataset.kind;

    const data =
      Object.fromEntries(
        new FormData(form)
      );

    Object.keys(data).forEach((key) => {
      if (data[key] === "") {
        delete data[key];
      }
    });

    const error =
      $("[data-inventory-error]");

    const submit =
      $("[data-inventory-submit]");

    error.textContent = "";

    submit.disabled = true;


    try {

      // --------------------------------------------------------
      // MATERIAL
      // --------------------------------------------------------

      if (kind === "material") {

        await request(
          `${API}materials/`,
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        );
      }


      // --------------------------------------------------------
      // WAREHOUSE
      // --------------------------------------------------------

      else if (kind === "warehouse") {

        await request(
          `${API}warehouses/`,
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        );
      }


      // --------------------------------------------------------
      // CATEGORY
      // --------------------------------------------------------

      else if (kind === "category") {

        await request(
          `${API}material-categories/`,
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        );
      }


      // --------------------------------------------------------
      // TRANSFER
      // --------------------------------------------------------

      else if (
        data.movement_type === "TRANSFER"
      ) {

        // Get the current user only when
        // we actually need to create a movement.

        if (!currentUser) {
          currentUser =
            await loadCurrentUser();
        }

        if (!currentUser?.id) {
          throw new Error(
            "Could not identify the current user. Please fix the /api/auth/me/ endpoint before recording movements."
          );
        }

        data.user = currentUser.id;

        data.quantity =
          Math.abs(
            Number(data.quantity)
          );

        delete data.warehouse;
        delete data.movement_type;

        await request(
          `${API}stock-movements/transfer/`,
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        );
      }


      // --------------------------------------------------------
      // NORMAL MOVEMENT
      // --------------------------------------------------------

      else {

        if (!currentUser) {
          currentUser =
            await loadCurrentUser();
        }

        if (!currentUser?.id) {
          throw new Error(
            "Could not identify the current user. Please fix the /api/auth/me/ endpoint before recording movements."
          );
        }

        data.user = currentUser.id;

        if (data.movement_type === "OUT") {
          data.quantity =
            -Math.abs(
              Number(data.quantity)
            );
        }

        await request(
          `${API}stock-movements/`,
          {
            method: "POST",
            body: JSON.stringify(data),
          }
        );
      }


      // --------------------------------------------------------
      // CLOSE + REFRESH
      // --------------------------------------------------------

      dialog.close();

      form.reset();


      const [materialsData, warehousesData, categoriesData] =
        await Promise.all([
          request(
            `${API}materials/?page_size=100`
          ),

          request(
            `${API}warehouses/?page_size=100`
          ),

          request(
            `${API}material-categories/?page_size=100`
          ),
        ]);

      materials = list(materialsData);
      warehouses = list(warehousesData);
      categories = list(categoriesData);

      await loadInventory();

    } catch (err) {

      error.textContent =
        err.message;

    } finally {

      submit.disabled = false;
    }
  }


  // ------------------------------------------------------------
  // INITIALIZE
  // ------------------------------------------------------------

  document.addEventListener(
    "DOMContentLoaded",
    async () => {

      try {

        // IMPORTANT:
        // We intentionally DO NOT request /api/auth/me/
        // here. That endpoint currently returns 500 because
        // UserSerializer expects User.role.

        const [
          materialsData,
          warehousesData,
          categoriesData,
        ] = await Promise.all([

          request(
            `${API}materials/?page_size=100`
          ),

          request(
            `${API}warehouses/?page_size=100`
          ),

          request(
            `${API}material-categories/?page_size=100`
          ),
        ]);


        materials =
          list(materialsData);

        warehouses =
          list(warehousesData);

        categories =
          list(categoriesData);


        // Warehouse filter

        const warehouseFilter =
          $("[data-inventory-warehouse]");

        if (warehouseFilter) {
          warehouseFilter.innerHTML =
            opts(
              warehouses,
              "",
              (item) => item.name,
              "Store: All"
            );
        }


        // Load actual stock

        await loadInventory();


      } catch (error) {

        console.error(
          "Inventory loading failed:",
          error
        );

        const rows =
          $("[data-inventory-rows]");

        if (rows) {
          rows.innerHTML = `
            <tr>
              <td colspan="8">
                <strong>
                  Could not load inventory:
                  ${esc(error.message)}
                </strong>
              </td>
            </tr>
          `;
        }
      }


      // --------------------------------------------------------
      // FILTERS
      // --------------------------------------------------------

      $("[data-inventory-search]")
        ?.addEventListener(
          "input",
          render
        );

      $("[data-inventory-warehouse]")
        ?.addEventListener(
          "change",
          render
        );

      $("[data-inventory-stock]")
        ?.addEventListener(
          "change",
          render
        );


      // --------------------------------------------------------
      // HEADER ACTIONS
      // --------------------------------------------------------

      document
        .querySelectorAll(
          "[data-inventory-action]"
        )
        .forEach((button) => {

          button.addEventListener(
            "click",
            () =>
              openDialog(
                button.dataset.inventoryAction
              )
          );

        });


      // --------------------------------------------------------
      // TABLE MOVEMENT BUTTON
      // --------------------------------------------------------

      $("[data-inventory-rows]")
        ?.addEventListener(
          "click",
          (event) => {

            const button =
              event.target.closest(
                "[data-movement-material]"
              );

            if (!button) return;

            openDialog(
              "movement",
              {
                material:
                  button.dataset
                    .movementMaterial,

                warehouse:
                  button.dataset
                    .movementWarehouse,
              }
            );
          }
        );


      // --------------------------------------------------------
      // CANCEL
      // --------------------------------------------------------

      $("[data-inventory-cancel]")
        ?.addEventListener(
          "click",
          () => {
            $("[data-inventory-dialog]")
              .close();
          }
        );


      // --------------------------------------------------------
      // FORM SUBMIT
      // --------------------------------------------------------

      $("[data-inventory-form]")
        ?.addEventListener(
          "submit",
          submitForm
        );


      // --------------------------------------------------------
      // NEW CATEGORY
      // --------------------------------------------------------

      const actions =
        document.querySelector(
          ".inventory-heading-actions"
        );

      if (
        actions &&
        !actions.querySelector(
          "[data-inventory-category]"
        )
      ) {

        actions.insertAdjacentHTML(
          "afterbegin",
          `
            <button
              class="quiet-button"
              type="button"
              data-inventory-category
            >
              New category
            </button>
          `
        );
      }


      document.addEventListener(
        "click",
        (event) => {

          if (
            !event.target.closest(
              "[data-inventory-category]"
            )
          ) {
            return;
          }

          openDialog("category");
        }
      );

    }
  );

})();
