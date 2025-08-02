/**
 * @file Saberis to Jobber data transformation module.
 *
 * This module is responsible for converting raw Saberis export data into a
 * structured format suitable for the Jobber API. It is designed to be the
 * single source of truth for this transformation logic on the client-side.
 */

// --- TypeScript Interfaces for Type Safety ---

/**
 * Represents a single, fully-formed line item ready to be sent to the backend.
 * This structure should be kept in sync with the backend's expectations.
 */
interface JobberLineItemPayload {
    name: string;
    quantity: number;
    description: string;
    unitCost: number; // This will hold our calculated COGS
    taxable: boolean;
    category: "PRODUCT" | "SERVICE";
    saveToProductsAndServices: boolean;
}

/**
 * Represents a raw line item from the Saberis JSON structure.
 */
interface SaberisRawLineItem {
    Type?: string;
    Description?: string;
    Quantity?: string | number;
    Cost?: string | number;
    [key: string]: any; // Allows for other properties
}

/**
 * Represents the overall structure of a Saberis export JSON object.
 */
interface SaberisExport {
    SaberisOrderDocument?: {
        Order?: {
            Group?: {
                Item?: SaberisRawLineItem[];
            };
        };
    };
}

// --- Transformation Logic ---

/**
 * Hashes a string using a simple algorithm to create a short, repeatable signature.
 * Note: This is NOT for cryptographic use.
 * @param str The string to hash.
 * @returns A short hexadecimal string signature.
 */
function simpleHash(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = (hash << 5) - hash + char;
        hash |= 0; // Convert to 32bit integer
    }
    // Convert to a positive hex string and take the first 6 characters
    return ('000000' + (hash >>> 0).toString(16)).slice(-6);
}

/**
 * Removes content within curly braces from a string.
 * @param text The text to process.
 * @returns Text with curly braces and their content removed.
 */
function removeCurlyBraces(text: string): string {
    return text.replace(/\{.*?\}/g, "");
}

/**
 * Builds the final array of Jobber line items from raw Saberis data.
 *
 * @param saberisData The raw JSON object from a Saberis export.
 * @param uiQuantity The quantity multiplier from the UI.
 * @param catalogMultipliers A dictionary mapping catalog IDs to their pricing multiplier.
 * @returns An array of fully-formed Jobber line item objects.
 */
export function buildLineItemsPayload(
    saberisData: SaberisExport,
    uiQuantity: number,
    catalogMultipliers: { [catalog: string]: number }
): JobberLineItemPayload[] {
    const finalLineItems: JobberLineItemPayload[] = [];
    const items = saberisData?.SaberisOrderDocument?.Order?.Group?.Item;

    if (!items) {
        return [];
    }

    let currentCatalog = "Unknown Catalog";
    let currentBrand = "Unknown Brand"; // You might need a way to get this
    const currentAttributes: { [key: string]: string } = {};

    for (const item of items) {
        const itemType = item.Type?.toLowerCase();
        const description = item.Description || "";

        if (itemType === 'text' && description.includes('=')) {
            const [key, value] = description.split('=', 2).map(s => s.trim());
            if (key === "Catalog") {
                currentCatalog = value;
                // In the future, you could have a lookup here for brand
                // currentBrand = getBrandForCatalog(value);
            }
            currentAttributes[key] = value;
        } else if (itemType === 'product') {
            const baseNameParts = [
                currentBrand,
                removeCurlyBraces(description)
            ];

            const descriptionParts: string[] = [];
            for (const [key, value] of Object.entries(currentAttributes)) {
                if (key.toLowerCase() === 'pricelevel' || key === 'Catalog' || key === 'Brand') {
                    continue;
                }
                descriptionParts.push(`${key}: ${value}`);
                // Assuming FIELDs_TO_PUT_IN_TITLE logic is still desired
                if (["Door Selection", "Cabinet Style"].includes(key)) {
                    baseNameParts.push(value);
                }
            }

            const baseProductName = baseNameParts.filter(Boolean).join(" | ");
            const jobberDescription = descriptionParts.join("\n");
            const signature = simpleHash(`${baseProductName}${jobberDescription}`);
            const finalProductName = `${baseProductName} | S2J(${signature})`;
            
            // Calculate final cost for this item
            const itemCost = parseFloat(String(item.Cost || 0));
            const multiplier = catalogMultipliers[currentCatalog] || 1.0;
            const unitCost = itemCost * multiplier;
            const quantity = parseFloat(String(item.Quantity || 1));

            finalLineItems.push({
                name: finalProductName,
                quantity: quantity * uiQuantity,
                description: jobberDescription,
                unitCost: unitCost, // Using the correctly calculated COGS!
                taxable: false,
                category: "PRODUCT",
                saveToProductsAndServices: true,
            });
        }
    }

    return finalLineItems;
}