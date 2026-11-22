/** Owner must explicitly type YES; ignore accidental case and surrounding spaces. */
export function ownerAuthorized(text) {
  return typeof text === "string" && text.trim().toUpperCase() === "YES";
}
