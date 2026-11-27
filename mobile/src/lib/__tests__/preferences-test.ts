import { preferenceErrorMessage, timezoneLabel } from "../preferences";

describe("timezoneLabel", () => {
  it("usa el nombre del bot para sus zonas", () => {
    expect(timezoneLabel("America/Bogota")).toBe("Bogotá");
    expect(timezoneLabel("America/New_York")).toBe("Nueva York");
  });

  it("muestra legible una zona que el bot no ofrece", () => {
    expect(timezoneLabel("America/Buenos_Aires")).toBe("America/Buenos Aires");
  });
});

describe("preferenceErrorMessage", () => {
  it("traduce el código de la base aunque venga dentro del texto", () => {
    expect(preferenceErrorMessage("ERROR: invalid_timezone (SQLSTATE 22023)")).toBe(
      "Esa zona horaria no está disponible.",
    );
    expect(preferenceErrorMessage("not_linked")).toMatch(/Vincula tu cuenta/);
  });

  it("da un mensaje genérico para lo desconocido", () => {
    expect(preferenceErrorMessage(undefined)).toBe("No se pudo guardar. Inténtalo de nuevo.");
    expect(preferenceErrorMessage("network down")).toBe("No se pudo guardar. Inténtalo de nuevo.");
  });
});
