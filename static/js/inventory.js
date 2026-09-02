(() => {
const API = "/api/inventory/";

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
            .find((cookie) =>
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


async function request(url, options = {}) {

    const response = await fetch(url, {

        credentials: "same-origin",

        ...options,

        headers: {

            Accept: "application/json",

            ...(options.method
                ? {
                    "Content-Type":
                        "application/json",

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
                    String(item.id) === String(value)
                        ? "selected"
                        : ""
                }>${esc(text(item))}</option>`
        )
        .join("");


function render() {

    const searchInput =
        $("[data-inventory-search]");

    const warehouseSelect =
        $("[data-inventory-warehouse]");

    const stockSelect =
        $("[data-inventory-stock]");

    const rowsContainer =
        $("[data-inventory-rows]");


    if (!rowsContainer) return;


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


    const stockFilter =
        stockSelect
            ? stockSelect.value
            : "";


    const rows =
        stocks.filter((stock) => {

            const matchesWarehouse =
                !warehouse ||
                String(stock.warehouse) ===
                String(warehouse);


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
                !query ||
                searchableText.includes(query);


            return (
                matchesWarehouse &&
                matchesStock &&
                matchesSearch
            );

        });


    if (!rows.length) {

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

            rows
                .map((stock) => {

                    const material =
                        materials.find(
                            (item) =>
                                String(item.id) ===
                                String(stock.material)
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


                    return `

                        <tr>

                            <td>

                                <strong>
                                    ${esc(
                                        stock.material_name
                                    )}
                                </strong>

                                <span>
                                    View details
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
                                —
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


    const itemsMetric =
        $("[data-inventory-metric=items]");

    const lowMetric =
        $("[data-inventory-metric=low]");

    const valueMetric =
        $("[data-inventory-metric=value]");

    const warehousesMetric =
        $("[data-inventory-metric=warehouses]");


    if (itemsMetric) {

        itemsMetric.textContent =
            materials.length;

    }


    if (lowMetric) {

        lowMetric.textContent =
            stocks.filter(
                (stock) =>
                    stock.is_low_stock
            ).length;

    }


    if (valueMetric) {

        const inventoryValue =
            stocks.reduce(
                (total, stock) => {

                    const material =
                        materials.find(
                            (item) =>
                                String(item.id) ===
                                String(stock.material)
                        );


                    const cost =
                        Number(
                            material?.standard_cost || 0
                        );


                    return (
                        total +
                        Number(
                            stock.quantity || 0
                        ) *
                        cost
                    );

                },
                0
            );


        valueMetric.textContent =
            money(inventoryValue);

    }


    if (warehousesMetric) {

        warehousesMetric.textContent =
            warehouses.length;

    }

}


function renderMovements() {

    const rowsContainer =
        $("[data-inventory-movement-rows]");

    const count =
        $("[data-inventory-movement-count]");


    if (!rowsContainer) return;


    if (count) {

        count.textContent =
            `${movements.length} movement${
                movements.length === 1
                    ? ""
                    : "s"
            }`;

    }


    const recentMovements =

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

            .slice(0, 10);


    if (!recentMovements.length) {

        rowsContainer.innerHTML = `

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


    rowsContainer.innerHTML =

        recentMovements

            .map((movement) => {

                const movementType =
                    movement.movement_type ||
                    "—";


                const statusClass =
                    movementType === "OUT"
                        ? "at-risk"
                        : "active";


                const date =
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
                                class="status ${statusClass}"
                            >

                                <i></i>

                                ${esc(
                                    movementType
                                )}

                            </span>

                        </td>


                        <td>
                            ${esc(
                                movement.quantity
                            )}
                        </td>


                        <td>
                            ${esc(
                                movement.reference
                            )}
                        </td>


                        <td>
                            ${esc(date)}
                        </td>

                    </tr>

                `;

            })

            .join("");

}


async function loadInventory() {

    const [
        stockData,
        movementData
    ] = await Promise.all([

        request(
            `${API}stocks/?page_size=100`
        ),

        request(
            `${API}stock-movements/?page_size=100`
        ),

    ]);


    stocks =
        list(stockData);


    movements =
        list(movementData);


    const today =
        new Date()
            .toISOString()
            .slice(0, 10);


    const transfersToday =
        movements.filter(
            (movement) =>
                movement.movement_type ===
                "TRANSFER" &&

                movement.movement_date
                    ?.startsWith(today)
        ).length;


    const transfersMetric =
        $("[data-inventory-metric=transfers]");


    if (transfersMetric) {

        transfersMetric.textContent =
            transfersToday;

    }


    render();

    renderMovements();

}


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


function renderMaterialsManagement() {

    const container =
        $("[data-material-management-rows]");


    if (!container) return;


    const search =
        $("[data-material-management-search]")
            ?.value
            .trim()
            .toLowerCase() || "";


    const filtered =
        materials.filter((material) => {

            const category =
                categories.find(
                    (item) =>
                        String(item.id) ===
                        String(material.category)
                );


            const text = [

                material.name,

                material.sku,

                category?.name,

                material.unit

            ]
                .join(" ")
                .toLowerCase();


            return (
                !search ||
                text.includes(search)
            );

        });


    if (!filtered.length) {

        container.innerHTML = `

            <tr>

                <td colspan="8">

                    <strong>
                        No materials found.
                    </strong>

                </td>

            </tr>

        `;

        return;

    }


    container.innerHTML =

        filtered

            .map((material) => {

                const category =
                    categories.find(
                        (item) =>
                            String(item.id) ===
                            String(
                                material.category
                            )
                    );


                const active =
                    material.is_active !== false;


                return `

                    <tr>

                        <td>

                            <strong>
                                ${esc(
                                    material.name
                                )}
                            </strong>

                            ${
                                material.description
                                    ? `
                                        <span>
                                            ${esc(
                                                material.description
                                            )}
                                        </span>
                                      `
                                    : ""
                            }

                        </td>


                        <td>
                            ${esc(
                                material.sku
                            )}
                        </td>


                        <td>
                            ${esc(
                                category?.name ||
                                material.category_name ||
                                "—"
                            )}
                        </td>


                        <td>
                            ${esc(
                                material.unit
                            )}
                        </td>


                        <td>
                            ${money(
                                material.standard_cost
                            )}
                        </td>


                        <td>
                            ${esc(
                                material.minimum_stock_level
                            )}
                        </td>


                        <td>

                            <span
                                class="status ${
                                    active
                                        ? "active"
                                        : "at-risk"
                                }"
                            >

                                <i></i>

                                ${
                                    active
                                        ? "Active"
                                        : "Inactive"
                                }

                            </span>

                        </td>


                        <td>

                            <div
                                class="inventory-row-actions"
                            >

                                <button
                                    type="button"
                                    class="quiet-button"
                                    data-edit-material="${esc(
                                        material.id
                                    )}"
                                >
                                    Edit
                                </button>


                                <button
                                    type="button"
                                    class="quiet-button danger-button"
                                    data-delete-material="${esc(
                                        material.id
                                    )}"
                                >
                                    Delete
                                </button>

                            </div>

                        </td>

                    </tr>

                `;

            })

            .join("");

}


function renderCategoriesManagement() {

    const container =
        $("[data-category-management-rows]");


    if (!container) return;


    const search =
        $("[data-category-management-search]")
            ?.value
            .trim()
            .toLowerCase() || "";


    const filtered =
        categories.filter((category) => {

            const text = [

                category.name,

                category.description

            ]
                .join(" ")
                .toLowerCase();


            return (
                !search ||
                text.includes(search)
            );

        });


    if (!filtered.length) {

        container.innerHTML = `

            <tr>

                <td colspan="3">

                    <strong>
                        No categories found.
                    </strong>

                </td>

            </tr>

        `;

        return;

    }


    container.innerHTML =

        filtered

            .map((category) => {

                return `

                    <tr>

                        <td>

                            <strong>
                                ${esc(
                                    category.name
                                )}
                            </strong>

                        </td>


                        <td>
                            ${esc(
                                category.description
                            )}
                        </td>


                        <td>

                            <div
                                class="inventory-row-actions"
                            >

                                <button
                                    type="button"
                                    class="quiet-button"
                                    data-edit-category="${esc(
                                        category.id
                                    )}"
                                >
                                    Edit
                                </button>


                                <button
                                    type="button"
                                    class="quiet-button danger-button"
                                    data-delete-category="${esc(
                                        category.id
                                    )}"
                                >
                                    Delete
                                </button>

                            </div>

                        </td>

                    </tr>

                `;

            })

            .join("");

}


function renderWarehousesManagement() {

    const container =
        $("[data-warehouse-management-rows]");


    if (!container) return;


    const search =
        $("[data-warehouse-management-search]")
            ?.value
            .trim()
            .toLowerCase() || "";


    const filtered =
        warehouses.filter((warehouse) => {

            const text = [

                warehouse.name,

                warehouse.location

            ]
                .join(" ")
                .toLowerCase();


            return (
                !search ||
                text.includes(search)
            );

        });


    if (!filtered.length) {

        container.innerHTML = `

            <tr>

                <td colspan="3">

                    <strong>
                        No warehouses found.
                    </strong>

                </td>

            </tr>

        `;

        return;

    }


    container.innerHTML =

        filtered

            .map((warehouse) => {

                return `

                    <tr>

                        <td>

                            <strong>
                                ${esc(
                                    warehouse.name
                                )}
                            </strong>

                        </td>


                        <td>
                            ${esc(
                                warehouse.location
                            )}
                        </td>


                        <td>

                            <div
                                class="inventory-row-actions"
                            >

                                <button
                                    type="button"
                                    class="quiet-button"
                                    data-edit-warehouse="${esc(
                                        warehouse.id
                                    )}"
                                >
                                    Edit
                                </button>


                                <button
                                    type="button"
                                    class="quiet-button danger-button"
                                    data-delete-warehouse="${esc(
                                        warehouse.id
                                    )}"
                                >
                                    Delete
                                </button>

                            </div>

                        </td>

                    </tr>

                `;

            })

            .join("");

}


function renderInventoryManagement() {

    renderMaterialsManagement();

    renderCategoriesManagement();

    renderWarehousesManagement();

}


function openDialog(kind, preset = {}) {

    const dialog =
        $("[data-inventory-dialog]");

    const fields =
        $("[data-inventory-fields]");


    dialog.dataset.kind =
        kind;


    dialog.dataset.id =
        preset.id || "";


    $("[data-inventory-error]")
        .textContent = "";


    if (kind === "material") {

        const editing =
            Boolean(preset.id);


        $("[data-inventory-title]")
            .textContent =
                editing
                    ? "Edit material"
                    : "Add material";


        $("[data-inventory-submit]")
            .textContent =
                editing
                    ? "Save changes"
                    : "Create material";


        fields.innerHTML = `

            <label>

                Material name

                <input
                    name="name"
                    value="${esc(
                        preset.name
                    )}"
                    required
                >

            </label>


            <label>

                SKU

                <input
                    name="sku"
                    value="${esc(
                        preset.sku
                    )}"
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
                        preset.category || "",
                        (item) => item.name,
                        "Select category"
                    )}

                </select>

            </label>


            <label>

                Unit

                <input
                    name="unit"
                    value="${esc(
                        preset.unit
                    )}"
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
                    value="${esc(
                        preset.standard_cost
                    )}"
                >

            </label>


            <label>

                Minimum stock

                <input
                    name="minimum_stock_level"
                    type="number"
                    min="0"
                    step="0.001"
                    value="${esc(
                        preset.minimum_stock_level ??
                        0
                    )}"
                >

            </label>


            <label>

                Status

                <select name="is_active">

                    <option
                        value="true"
                        ${
                            preset.is_active !== false
                                ? "selected"
                                : ""
                        }
                    >
                        Active
                    </option>

                    <option
                        value="false"
                        ${
                            preset.is_active === false
                                ? "selected"
                                : ""
                        }
                    >
                        Inactive
                    </option>

                </select>

            </label>


            <label
                style="grid-column:1/-1"
            >

                Description

                <textarea
                    name="description"
                >${esc(
                    preset.description
                )}</textarea>

            </label>

        `;

    }


    else if (kind === "warehouse") {

        const editing =
            Boolean(preset.id);


        $("[data-inventory-title]")
            .textContent =
                editing
                    ? "Edit warehouse"
                    : "New warehouse";


        $("[data-inventory-submit]")
            .textContent =
                editing
                    ? "Save changes"
                    : "Create warehouse";


        fields.innerHTML = `

            <label>

                Warehouse name

                <input
                    name="name"
                    value="${esc(
                        preset.name
                    )}"
                    required
                >

            </label>


            <label>

                Location

                <input
                    name="location"
                    value="${esc(
                        preset.location
                    )}"
                >

            </label>

        `;

    }


    else if (kind === "category") {

        const editing =
            Boolean(preset.id);


        $("[data-inventory-title]")
            .textContent =
                editing
                    ? "Edit material category"
                    : "New material category";


        $("[data-inventory-submit]")
            .textContent =
                editing
                    ? "Save changes"
                    : "Create category";


        fields.innerHTML = `

            <label>

                Category name

                <input
                    name="name"
                    value="${esc(
                        preset.name
                    )}"
                    required
                >

            </label>


            <label
                style="grid-column:1/-1"
            >

                Description

                <textarea
                    name="description"
                >${esc(
                    preset.description
                )}</textarea>

            </label>

        `;

    }


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


            <label
                style="grid-column:1/-1"
            >

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
                    event.target.value ===
                    "TRANSFER";


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
                    .forEach(
                        (field) => {

                            field.required =
                                transfer;

                        }
                    );

            }
        );

    }


    dialog.showModal();

}


async function submitForm(event) {

    event.preventDefault();


    const form =
        event.currentTarget;


    const dialog =
        $("[data-inventory-dialog]");


    const kind =
        dialog.dataset.kind;


    const id =
        dialog.dataset.id;


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

        if (kind === "material") {

            data.is_active =
                data.is_active !== "false";


            const url =
                id
                    ? `${API}materials/${id}/`
                    : `${API}materials/`;


            await request(
                url,
                {

                    method:
                        id
                            ? "PATCH"
                            : "POST",

                    body:
                        JSON.stringify(data),

                }
            );

        }


        else if (kind === "warehouse") {

            const url =
                id
                    ? `${API}warehouses/${id}/`
                    : `${API}warehouses/`;


            await request(
                url,
                {

                    method:
                        id
                            ? "PATCH"
                            : "POST",

                    body:
                        JSON.stringify(data),

                }
            );

        }


        else if (kind === "category") {

            const url =
                id
                    ? `${API}material-categories/${id}/`
                    : `${API}material-categories/`;


            await request(
                url,
                {

                    method:
                        id
                            ? "PATCH"
                            : "POST",

                    body:
                        JSON.stringify(data),

                }
            );

        }


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
                    "Could not identify the current user. Please fix the /api/auth/me/ endpoint before recording movements."
                );

            }


            data.user =
                currentUser.id;


            data.quantity =
                Math.abs(
                    Number(
                        data.quantity
                    )
                );


            delete data.warehouse;

            delete data.movement_type;


            await request(
                `${API}stock-movements/transfer/`,
                {

                    method: "POST",

                    body:
                        JSON.stringify(data),

                }
            );

        }


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

                    body:
                        JSON.stringify(data),

                }
            );

        }


        dialog.close();

        form.reset();


        await loadReferenceData();


        renderInventoryManagement();

        render();


        await loadInventory();


    } catch (err) {

        error.textContent =
            err.message;

    } finally {

        submit.disabled = false;

    }

}


async function deleteInventoryItem(
    endpoint,
    id,
    type
) {

    const confirmed =
        window.confirm(
            `Are you sure you want to delete this ${type}?`
        );


    if (!confirmed) return;


    try {

        await request(
            `${API}${endpoint}/${id}/`,
            {
                method: "DELETE",
            }
        );


        await loadReferenceData();


        renderInventoryManagement();

        render();

    } catch (error) {

        window.alert(
            `Could not delete ${type}: ${error.message}`
        );

    }

}


async function loadReferenceData() {

    const [
        materialsData,
        warehousesData,
        categoriesData
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


    const warehouseFilter =
        $("[data-inventory-warehouse]");


    if (warehouseFilter) {

        const currentValue =
            warehouseFilter.value;


        warehouseFilter.innerHTML =
            opts(
                warehouses,
                currentValue,
                (item) => item.name,
                "Store: All"
            );

    }

}


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        try {

            await loadReferenceData();


            renderInventoryManagement();


            await loadInventory();


        } catch (error) {

            console.error(
                "Inventory loading failed:",
                error
            );


            // Previously only the stock/movements tables showed this
            // error — materials/categories/warehouses stayed stuck on
            // their static "Loading…" placeholder forever with no
            // visible error at all. loadReferenceData() failing (e.g.
            // a 401/403 because there's no authenticated session yet)
            // threw before renderInventoryManagement() ever ran, and
            // nothing told the user why. Show the same error on all
            // five tables now.

            const errorRow = (colspan, label) => `
                <tr>
                    <td colspan="${colspan}">
                        <strong>
                            Could not load ${label}: ${esc(error.message)}
                        </strong>
                    </td>
                </tr>
            `;

            const targets = [
                ["[data-inventory-rows]", 8, "inventory"],
                ["[data-inventory-movement-rows]", 6, "movements"],
                ["[data-material-management-rows]", 8, "materials"],
                ["[data-category-management-rows]", 3, "categories"],
                ["[data-warehouse-management-rows]", 3, "warehouses"],
            ];

            targets.forEach(([selector, colspan, label]) => {
                const el = $(selector);
                if (el) {
                    el.innerHTML = errorRow(colspan, label);
                }
            });

        }


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


        $("[data-inventory-cancel]")
            ?.addEventListener(
                "click",
                () => {

                    $("[data-inventory-dialog]")
                        .close();

                }
            );


        $("[data-inventory-form]")
            ?.addEventListener(
                "submit",
                submitForm
            );


        $("[data-material-management-search]")
            ?.addEventListener(
                "input",
                renderMaterialsManagement
            );


        $("[data-category-management-search]")
            ?.addEventListener(
                "input",
                renderCategoriesManagement
            );


        $("[data-warehouse-management-search]")
            ?.addEventListener(
                "input",
                renderWarehousesManagement
            );


        document
            .querySelectorAll(
                "[data-inventory-management-tab]"
            )
            .forEach((button) => {

                button.addEventListener(
                    "click",
                    () => {

                        const target =
                            button.dataset
                                .inventoryManagementTab;


                        document
                            .querySelectorAll(
                                "[data-inventory-management-tab]"
                            )
                            .forEach(
                                (item) => {

                                    item.classList.remove(
                                        "active"
                                    );

                                }
                            );


                        document
                            .querySelectorAll(
                                "[data-inventory-management-content]"
                            )
                            .forEach(
                                (content) => {

                                    content.classList.remove(
                                        "active"
                                    );

                                }
                            );


                        button.classList.add(
                            "active"
                        );


                        $(
                            `[data-inventory-management-content="${target}"]`
                        )
                            ?.classList.add(
                                "active"
                            );

                    }
                );

            });


        document.addEventListener(
            "click",
            async (event) => {

                const editMaterial =
                    event.target.closest(
                        "[data-edit-material]"
                    );


                if (editMaterial) {

                    const material =
                        materials.find(
                            (item) =>
                                String(item.id) ===
                                String(
                                    editMaterial
                                        .dataset
                                        .editMaterial
                                )
                        );


                    if (material) {

                        openDialog(
                            "material",
                            material
                        );

                    }


                    return;

                }


                const editCategory =
                    event.target.closest(
                        "[data-edit-category]"
                    );


                if (editCategory) {

                    const category =
                        categories.find(
                            (item) =>
                                String(item.id) ===
                                String(
                                    editCategory
                                        .dataset
                                        .editCategory
                                )
                        );


                    if (category) {

                        openDialog(
                            "category",
                            category
                        );

                    }


                    return;

                }


                const editWarehouse =
                    event.target.closest(
                        "[data-edit-warehouse]"
                    );


                if (editWarehouse) {

                    const warehouse =
                        warehouses.find(
                            (item) =>
                                String(item.id) ===
                                String(
                                    editWarehouse
                                        .dataset
                                        .editWarehouse
                                )
                        );


                    if (warehouse) {

                        openDialog(
                            "warehouse",
                            warehouse
                        );

                    }


                    return;

                }


                const deleteMaterial =
                    event.target.closest(
                        "[data-delete-material]"
                    );


                if (deleteMaterial) {

                    await deleteInventoryItem(
                        "materials",
                        deleteMaterial.dataset
                            .deleteMaterial,
                        "material"
                    );


                    return;

                }


                const deleteCategory =
                    event.target.closest(
                        "[data-delete-category]"
                    );


                if (deleteCategory) {

                    await deleteInventoryItem(
                        "material-categories",
                        deleteCategory.dataset
                            .deleteCategory,
                        "category"
                    );


                    return;

                }


                const deleteWarehouse =
                    event.target.closest(
                        "[data-delete-warehouse]"
                    );


                if (deleteWarehouse) {

                    await deleteInventoryItem(
                        "warehouses",
                        deleteWarehouse.dataset
                            .deleteWarehouse,
                        "warehouse"
                    );

                }

            }
        );

    }
);

})();