export const DEMO_CITIES = [
  "Maastricht",
  "Valkenburg",
  "Heerlen",
  "Sittard",
  "Roermond",
  "Genk",
  "Hasselt",
  "Liège",
  "Aachen",
  "Amsterdam",
  "Rotterdam",
  "Utrecht",
  "Eindhoven",
  "Delft",
] as const

export const OTHER_CITY_VALUE = "__other__"

export type DemoCity = (typeof DEMO_CITIES)[number]
