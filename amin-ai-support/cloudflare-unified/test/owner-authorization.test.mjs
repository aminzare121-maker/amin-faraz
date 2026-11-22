import test from "node:test";
import assert from "node:assert/strict";
import { ownerAuthorized } from "../windows-setup/owner-authorization.mjs";
test("accepts owner consent with lowercase, uppercase, or extra whitespace", () => {
  for(const text of ["YES","yes","Yes","  yes  "," yEs\r"]) assert.equal(ownerAuthorized(text),true);
});
test("rejects blank, non-consent and dangerous lookalikes", () => {
  for(const text of ["","no","Y","yess","YES please","YES;foo",null,undefined]) assert.equal(ownerAuthorized(text),false);
});
