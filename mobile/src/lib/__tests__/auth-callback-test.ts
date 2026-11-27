import { readCallbackParams } from "../auth-callback";

test("con ?code= se canjea el código", () => {
  expect(readCallbackParams({ code: "abc" })).toEqual({ kind: "code", code: "abc" });
  expect(readCallbackParams({ code: ["abc", "def"] })).toEqual({ kind: "code", code: "abc" });
});

test("un enlace vencido o sin código es un error", () => {
  expect(readCallbackParams({ error: "access_denied", error_code: "otp_expired" })).toEqual({
    kind: "error",
  });
  expect(readCallbackParams({ code: "abc", error_code: "otp_expired" })).toEqual({ kind: "error" });
  expect(readCallbackParams({})).toEqual({ kind: "error" });
});
