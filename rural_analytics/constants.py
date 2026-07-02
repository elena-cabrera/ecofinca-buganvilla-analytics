"""Domain constants for rural house reservation analytics."""

COLUMN_ALIASES: dict[str, list[str]] = {
    "casa": ["casa"],
    "nombre": ["nombre"],
    "entrada": ["entrada"],
    "salida": ["salida"],
    "pais": ["país", "pais", "país "],
    "noches": ["noches"],
    "pax": ["pax"],
    "descuento": ["dto. %", "dto.%", "dto", "descuento"],
    "precio": ["precio"],
    "comision": ["comisión", "comision"],
    "forma_pago": ["f-pago", "f. pago", "forma pago", "forma_pago"],
    "tour_operador": ["tour operador", "operador", "tour_operador"],
}

KNOWN_CASAS = {
    "el olivo",
    "olivo",
    "el guayabo",
    "guayabo",
    "almendro",
    "el almendro",
    "buganvilla",
    "el buganvilla",
}

KNOWN_OPERADORES = {
    "privado",
    "booking",
    "mts",
    "airbnb",
    "expedia",
    "vrbo",
    "directo",
}

KNOWN_FORMAS_PAGO = {
    "efectivo",
    "visa",
    "transf.bco",
    "transferencia",
    "airbnb",
    "booking",
    "bizum",
    "paypal",
}

KNOWN_PAISES = {
    "españa",
    "espana",
    "reino unido",
    "países bajos",
    "paises bajos",
    "francia",
    "italia",
    "alemania",
    "portugal",
    "croacia",
    "belgica",
    "bélgica",
    "suiza",
    "irlanda",
    "austria",
    "polonia",
    "suecia",
    "noruega",
    "dinamarca",
    "estados unidos",
    "canadá",
    "canada",
}

MONTH_NAMES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
