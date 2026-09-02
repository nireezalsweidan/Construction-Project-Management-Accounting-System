(() => {

    const API = "/api/inventory/";

    const PAGE_SIZE = 8;


    const $ = (selector) =>
        document.querySelector(selector);


    const list = (data) =>
        Array.isArray(data)
            ? data
            : (data?.results || []);


    const esc = (value) =>
        String(value ?? "—").replace(
            /[&<>"']/g,
            (char) => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            })[char]
        );


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
                .find(
                    (cookie) =>
                        cookie.startsWith("csrftoken=")
                )
                ?.split("=")[1] || ""
        );


    let stocks = [];
    let materials = [];
    let warehouses = [];
    let categories = [];
    let movements = [];

    let currentUser = null;

    let currentPage = 1;


    /* =========================================================
       API REQUEST
       ========================================================= */

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


        const data =
            await response
                .json()
                .catch(() => ({}));


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


    /* =========================================================
       HELPERS
       ========================================================= */

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
                    `<option value="${esc(item.id)}"
                        ${item.id === value ? "selected" : ""}>
                        ${esc(text(item))}
                    </option>`
            )
            .join("");


    function getMaterial(id) {

        return materials.find(
            (item) => String(item.id) === String(id)
        );

    }


    function getWarehouse(id) {

        return warehouses.find(
            (item) => String(item.id) === String(id)
        );

    }


    function getCategory(id) {

        return categories.find(
            (item) => String(item.id) === String(id)
        );

    }


    /* =========================================================
       FILTERED STOCK
       ========================================================= */

    function getFilteredStocks() {

        const searchInput =
            $("[data-inventory-search]");

        const warehouseSelect =
            $("[data-inventory-warehouse]");

        const categorySelect =
            $("[data-inventory-category]");

        const stockSelect =
            $("[data-inventory-stock]");


        const query =
            searchInput
                ? searchInput.value
                    .trim()
                    .toLowerCase()
                : "";


        const warehouse =
            warehouseSelect
                ? warehouseSelect.value
                : "";


        const category =
            categorySelect
                ? categorySelect.value
                : "";


        const stockFilter =
            stockSelect
                ? stockSelect.value
                : "";


        return stocks.filter((stock) => {

            const material =
                getMaterial(stock.material);


            const matchesWarehouse =
                !warehouse ||
                String(stock.warehouse) ===
                    String(warehouse);


            const matchesCategory =
                !category ||
                String(material?.category) ===
                    String(category);


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

                material?.name,

                material?.sku,

            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();


            const matchesSearch =
                !query ||
                searchableText.includes(query);


            return (
                matchesWarehouse &&
                matchesCategory &&
                matchesStock &&
                matchesSearch
            );

        });

    }


    /* =========================================================
       INVENTORY TABLE
       ========================================================= */

    function render() {

        const rowsContainer =
            $("[data-inventory-rows]");


        if (!rowsContainer) return;


        const filtered =
            getFilteredStocks();


        const total =
            filtered.length;


        const totalPages =
            Math.max(
                1,
                Math.ceil(
                    total / PAGE_SIZE
                )
            );


        if (currentPage > totalPages) {
            currentPage = totalPages;
        }


        const start =
            (currentPage - 1) *
            PAGE_SIZE;


        const pageRows =
            filtered.slice(
                start,
                start + PAGE_SIZE
            );


        if (!pageRows.length) {

            rowsContainer.innerHTML = `
                <tr>
                    <td colspan="8">
                        <strong>
                            No stock balances found.
                        </strong>
                    </td>
                </tr>
            `;

        } else {

            rowsContainer.innerHTML =
                pageRows
                    .map((stock) => {

                        const material =
                            getMaterial(
                                stock.material
                            );


                        const unitCost =
                            Number(
                                material?.standard_cost || 0
                            );


                        const statusClass =
                            stock.is_low_stock
                                ? "at-risk"
                                : "active";


                        const statusText =
                            stock.is_low_stock
                                ? "Low stock"
                                : "In stock";


                        const reserved =
                            stock.reserved_quantity ??
                            stock.reserved ??
                            stock.quantity_reserved;


                        const reservedDisplay =
                            reserved !== undefined &&
                            reserved !== null
                                ? esc(reserved)
                                : "—";


                        return `
                            <tr>

                                <td>
                                    <strong>
                                        ${esc(
                                            stock.material_name
                                        )}
                                    </strong>

                                    <span>
                                        ${esc(
                                            material?.unit ||
                                            ""
                                        )}
                                    </span>
                                </td>


                                <td>
                                    ${esc(
                                        stock.material_sku
                                    )}
                                </td>


                                <td>
                                    ${esc(
                                        stock.warehouse_name
                                    )}
                                </td>


                                <td>
                                    ${esc(
                                        stock.quantity
                                    )}
                                </td>


                                <td>
                                    ${reservedDisplay}
                                </td>


                                <td>
                                    ${esc(
                                        stock.minimum_stock_level
                                    )}
                                </td>


                                <td>

                                    <span
                                        class="status ${statusClass}"
                                    >
                                        <i></i>

                                        ${statusText}
                                    </span>

                                </td>


                                <td>

                                    <button
                                        class="quiet-button"
                                        type="button"

                                        data-movement-material="${esc(
                                            stock.material
                                        )}"

                                        data-movement-warehouse="${esc(
                                            stock.warehouse
                                        )}"
                                    >
                                        Record
                                    </button>

                                </td>

                            </tr>
                        `;

                    })
                    .join("");

        }


        renderPagination(
            total,
            totalPages
        );


        renderMetrics();

    }


    /* =========================================================
       PAGINATION
       ========================================================= */

    function renderPagination(
        total,
        totalPages
    ) {

        const count =
            $("[data-inventory-count]");

        const pages =
            $("[data-inventory-pages]");

        const previous =
            $("[data-inventory-prev]");

        const next =
            $("[data-inventory-next]");


        const start =
            total === 0
                ? 0
                : (currentPage - 1) *
                    PAGE_SIZE + 1;


        const end =
            Math.min(
                currentPage * PAGE_SIZE,
                total
            );


        if (count) {

            count.textContent =
                `Showing ${start}-${end} of ${total} records`;

        }


        if (previous) {

            previous.disabled =
                currentPage <= 1;

        }


        if (next) {

            next.disabled =
                currentPage >= totalPages;

        }


        if (!pages) return;


        pages.innerHTML =
            Array.from(
                { length: totalPages },
                (_, index) => {

                    const page =
                        index + 1;


                    return `
                        <button
                            type="button"
                            class="quiet-button
                                ${page === currentPage
                                    ? "active"
                                    : ""}"

                            data-page="${page}"
                        >
                            ${page}
                        </button>
                    `;

                }
            )
            .join("");

    }


    /* =========================================================
       METRICS
       ========================================================= */

    function renderMetrics() {

        const itemsMetric =
            $("[data-inventory-metric=items]");


        const lowMetric =
            $("[data-inventory-metric=low]");


        const valueMetric =
            $("[data-inventory-metric=value]");


        const warehousesMetric =
            $("[data-inventory-metric=warehouses]");


        if (itemsMetric) {

            const uniqueMaterials =
                new Set(
                    stocks.map(
                        (stock) =>
                            stock.material
                    )
                );

            itemsMetric.textContent =
                uniqueMaterials.size;

        }


        if (lowMetric) {

            lowMetric.textContent =
                stocks.filter(
                    (stock) =>
                        stock.is_low_stock
                ).length;

        }


        if (warehousesMetric) {

            warehousesMetric.textContent =
                warehouses.length;

        }


        if (valueMetric) {

            const inventoryValue =
                stocks.reduce(
                    (total, stock) => {

                        const material =
                            getMaterial(
                                stock.material
                            );


                        const cost =
                            Number(
                                material?.standard_cost ||
                                0
                            );


                        return (
                            total +
                            Number(
                                stock.quantity || 0
                            ) * cost
                        );

                    },
                    0
                );


            valueMetric.textContent =
                money(inventoryValue);

        }

    }


    /* =========================================================
       MOVEMENTS TABLE
       ========================================================= */

    function renderMovements() {

        const container =
            $("[data-inventory-movement-rows]");


        const count =
            $("[data-inventory-movement-count]");


        if (!container) return;


        if (count) {

            count.textContent =
                `${movements.length} movement${
                    movements.length === 1
                        ? ""
                        : "s"
                }`;

        }


        const recent =
            [...movements]
                .sort(
                    (a, b) =>
                        new Date(
                            b.movement_date || 0
                        ) -
                        new Date(
                            a.movement_date || 0
                        )
                )
                .slice(0, 8);


        if (!recent.length) {

            container.innerHTML = `
                <tr>
                    <td colspan="6">
                        <strong>
                            No stock movements found.
                        </strong>
                    </td>
                </tr>
            `;

            return;

        }


        container.innerHTML =
            recent
                .map((movement) => {

                    const type =
                        movement.movement_type ||
                        "—";


                    const typeClass =
                        type === "OUT"
                            ? "at-risk"
                            : "active";


                    const quantity =
                        Number(
                            movement.quantity || 0
                        );


                    const formattedDate =
                        movement.movement_date
                            ? new Date(
                                movement.movement_date
                            ).toLocaleDateString()
                            : "—";


                    return `
                        <tr>

                            <td>
                                <strong>
                                    ${esc(
                                        movement.material_name
                                    )}
                                </strong>
                            </td>


                            <td>
                                ${esc(
                                    movement.warehouse_name
                                )}
                            </td>


                            <td>
                                <span
                                    class="status ${typeClass}"
                                >
                                    <i></i>
                                    ${esc(type)}
                                </span>
                            </td>


                            <td>
                                ${esc(quantity)}
                            </td>


                            <td>
                                ${esc(
                                    movement.reference
                                )}
                            </td>


                            <td>
                                ${esc(
                                    formattedDate
                                )}
                            </td>

                        </tr>
                    `;

                })
                .join("");

    }


    /* =========================================================
       LOAD ALL INVENTORY DATA
       ========================================================= */

    async function loadInventoryData() {

        const [
            materialsData,
            warehousesData,
            categoriesData,
            stocksData,
            movementsData,
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

            request(
                `${API}stocks/?page_size=100`
            ),

            request(
                `${API}stock-movements/?page_size=100`
            ),

        ]);


        materials =
            list(materialsData);


        warehouses =
            list(warehousesData);


        categories =
            list(categoriesData);


        stocks =
            list(stocksData);


        movements =
            list(movementsData);


        populateFilters();


        render();

        renderMovements();

    }


    /* =========================================================
       FILTER OPTIONS
       ========================================================= */

    function populateFilters() {

        const warehouseFilter =
            $("[data-inventory-warehouse]");


        const categoryFilter =
            $("[data-inventory-category]");


        if (warehouseFilter) {

            warehouseFilter.innerHTML =
                opts(
                    warehouses,
                    "",
                    (item) => item.name,
                    "Warehouse: All"
                );

        }


        if (categoryFilter) {

            categoryFilter.innerHTML =
                opts(
                    categories,
                    "",
                    (item) => item.name,
                    "Category: All"
                );

        }

    }


    /* =========================================================
       CURRENT USER
       ========================================================= */

    async function loadCurrentUser() {

        try {

            currentUser =
                await request(
                    "/api/auth/me/"
                );


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


    /* =========================================================
       DIALOG
       ========================================================= */

    function openDialog(
        kind,
        preset = {}
    ) {

        const dialog =
            $("[data-inventory-dialog]");


        const fields =
            $("[data-inventory-fields]");


        dialog.dataset.kind =
            kind;


        $("[data-inventory-error]")
            .textContent = "";


        /* -----------------------------------------------------
           MATERIAL
           ----------------------------------------------------- */

        if (kind === "material") {

            $("[data-inventory-title]")
                .textContent =
                "Add material";


            $("[data-inventory-submit]")
                .textContent =
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

                    <textarea
                        name="description"
                    ></textarea>
                </label>

            `;

        }


        /* -----------------------------------------------------
           WAREHOUSE
           ----------------------------------------------------- */

        else if (kind === "warehouse") {

            $("[data-inventory-title]")
                .textContent =
                "New warehouse";


            $("[data-inventory-submit]")
                .textContent =
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


        /* -----------------------------------------------------
           CATEGORY
           ----------------------------------------------------- */

        else if (kind === "category") {

            $("[data-inventory-title]")
                .textContent =
                "New material category";


            $("[data-inventory-submit]")
                .textContent =
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


        /* -----------------------------------------------------
           STOCK MOVEMENT
           ----------------------------------------------------- */

        else {

            $("[data-inventory-title]")
                .textContent =
                "Record stock movement";


            $("[data-inventory-submit]")
                .textContent =
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

                    <select
                        name="from_warehouse"
                    >

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

                    <select
                        name="to_warehouse"
                    >

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
                updateMovementFields
            );

        }


        dialog.showModal();

    }


    /* =========================================================
       MOVEMENT TYPE UI
       ========================================================= */

    function updateMovementFields(event) {

        const fields =
            $("[data-inventory-fields]");


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


        source.hidden =
            transfer;


        transferFields.forEach(
            (field) => {

                field.hidden =
                    !transfer;

            }
        );


        warehouse.required =
            !transfer;


        fields
            .querySelectorAll(
                "[name=from_warehouse],[name=to_warehouse]"
            )
            .forEach((field) => {

                field.required =
                    transfer;

            });

    }


    /* =========================================================
       CREATE / SAVE
       ========================================================= */

    async function submitForm(event) {

        event.preventDefault();


        const form =
            event.currentTarget;


        const dialog =
            $("[data-inventory-dialog]");


        const kind =
            dialog.dataset.kind;


        const data =
            Object.fromEntries(
                new FormData(form)
            );


        Object.keys(data).forEach(
            (key) => {

                if (data[key] === "") {

                    delete data[key];

                }

            }
        );


        const error =
            $("[data-inventory-error]");


        const submit =
            $("[data-inventory-submit]");


        error.textContent =
            "";


        submit.disabled =
            true;


        try {

            /* -------------------------------------------------
               MATERIAL
               ------------------------------------------------- */

            if (kind === "material") {

                await request(
                    `${API}materials/`,
                    {
                        method: "POST",
                        body: JSON.stringify(data),
                    }
                );

            }


            /* -------------------------------------------------
               WAREHOUSE
               ------------------------------------------------- */

            else if (kind === "warehouse") {

                await request(
                    `${API}warehouses/`,
                    {
                        method: "POST",
                        body: JSON.stringify(data),
                    }
                );

            }


            /* -------------------------------------------------
               CATEGORY
               ------------------------------------------------- */

            else if (kind === "category") {

                await request(
                    `${API}material-categories/`,
                    {
                        method: "POST",
                        body: JSON.stringify(data),
                    }
                );

            }


            /* -------------------------------------------------
               TRANSFER
               ------------------------------------------------- */

            else if (
                data.movement_type ===
                "TRANSFER"
            ) {

                if (!currentUser) {

                    currentUser =
                        await loadCurrentUser();

                }


                if (!currentUser?.id) {

                    throw new Error(
                        "Could not identify the current user."
                    );

                }


                data.user =
                    currentUser.id;


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


            /* -------------------------------------------------
               NORMAL MOVEMENT
               ------------------------------------------------- */

            else {

                if (!currentUser) {

                    currentUser =
                        await loadCurrentUser();

                }


                if (!currentUser?.id) {

                    throw new Error(
                        "Could not identify the current user."
                    );

                }


                data.user =
                    currentUser.id;


                if (
                    data.movement_type ===
                    "OUT"
                ) {

                    data.quantity =
                        -Math.abs(
                            Number(
                                data.quantity
                            )
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


            /* -------------------------------------------------
               REFRESH
               ------------------------------------------------- */

            dialog.close();

            form.reset();


            await loadInventoryData();


        } catch (err) {

            error.textContent =
                err.message;

        } finally {

            submit.disabled =
                false;

        }

    }


    /* =========================================================
       CLEAR FILTERS
       ========================================================= */

    function clearFilters() {

        const search =
            $("[data-inventory-search]");

        const warehouse =
            $("[data-inventory-warehouse]");

        const category =
            $("[data-inventory-category]");

        const stock =
            $("[data-inventory-stock]");


        if (search) {
            search.value = "";
        }


        if (warehouse) {
            warehouse.value = "";
        }


        if (category) {
            category.value = "";
        }


        if (stock) {
            stock.value = "";
        }


        currentPage = 1;


        render();

    }


    /* =========================================================
       INITIALIZE
       ========================================================= */

    document.addEventListener(
        "DOMContentLoaded",
        async () => {

            try {

                await loadInventoryData();

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
                                    ${esc(
                                        error.message
                                    )}
                                </strong>
                            </td>
                        </tr>
                    `;

                }

            }


            /* -------------------------------------------------
               Search
               ------------------------------------------------- */

            $("[data-inventory-search]")
                ?.addEventListener(
                    "input",
                    () => {

                        currentPage = 1;

                        render();

                    }
                );


            /* -------------------------------------------------
               Warehouse
               ------------------------------------------------- */

            $("[data-inventory-warehouse]")
                ?.addEventListener(
                    "change",
                    () => {

                        currentPage = 1;

                        render();

                    }
                );


            /* -------------------------------------------------
               Category
               ------------------------------------------------- */

            $("[data-inventory-category]")
                ?.addEventListener(
                    "change",
                    () => {

                        currentPage = 1;

                        render();

                    }
                );


            /* -------------------------------------------------
               Stock status
               ------------------------------------------------- */

            $("[data-inventory-stock]")
                ?.addEventListener(
                    "change",
                    () => {

                        currentPage = 1;

                        render();

                    }
                );


            /* -------------------------------------------------
               Clear filters
               ------------------------------------------------- */

            $("[data-inventory-clear]")
                ?.addEventListener(
                    "click",
                    clearFilters
                );


            /* -------------------------------------------------
               Header actions
               ------------------------------------------------- */

            document
                .querySelectorAll(
                    "[data-inventory-action]"
                )
                .forEach((button) => {

                    button.addEventListener(
                        "click",
                        () => {

                            openDialog(
                                button.dataset
                                    .inventoryAction
                            );

                        }
                    );

                });


            /* -------------------------------------------------
               Movement button in table
               ------------------------------------------------- */

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


            /* -------------------------------------------------
               Pagination
               ------------------------------------------------- */

            $("[data-inventory-prev]")
                ?.addEventListener(
                    "click",
                    () => {

                        if (currentPage > 1) {

                            currentPage--;

                            render();

                        }

                    }
                );


            $("[data-inventory-next]")
                ?.addEventListener(
                    "click",
                    () => {

                        const total =
                            getFilteredStocks()
                                .length;


                        const totalPages =
                            Math.max(
                                1,
                                Math.ceil(
                                    total /
                                    PAGE_SIZE
                                )
                            );


                        if (
                            currentPage <
                            totalPages
                        ) {

                            currentPage++;

                            render();

                        }

                    }
                );


            $("[data-inventory-pages]")
                ?.addEventListener(
                    "click",
                    (event) => {

                        const button =
                            event.target.closest(
                                "[data-page]"
                            );


                        if (!button) return;


                        currentPage =
                            Number(
                                button.dataset.page
                            );


                        render();

                    }
                );


            /* -------------------------------------------------
               Cancel
               ------------------------------------------------- */

            $("[data-inventory-cancel]")
                ?.addEventListener(
                    "click",
                    () => {

                        $(
                            "[data-inventory-dialog]"
                        ).close();

                    }
                );


            /* -------------------------------------------------
               Submit
               ------------------------------------------------- */

            $("[data-inventory-form]")
                ?.addEventListener(
                    "submit",
                    submitForm
                );

        }
    );

})();