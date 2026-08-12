import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createRequest, type CreateRequestPayload } from "../api";

const CITY_MIN_LENGTH = 1;
const CITY_MAX_LENGTH = 100;
const DISTRICT_MIN_LENGTH = 1;
const DISTRICT_MAX_LENGTH = 100;
const ADDRESS_MIN_LENGTH = 5;
const ADDRESS_MAX_LENGTH = 500;
const MESSAGE_MIN_LENGTH = 10;
const MESSAGE_MAX_LENGTH = 2000;
const LATITUDE_MIN = -90;
const LATITUDE_MAX = 90;
const LONGITUDE_MIN = -180;
const LONGITUDE_MAX = 180;

const CITY_HELPER_ID = "city-helper";
const CITY_ERROR_ID = "city-error";
const DISTRICT_HELPER_ID = "district-helper";
const DISTRICT_ERROR_ID = "district-error";
const LATITUDE_HELPER_ID = "latitude-helper";
const LONGITUDE_HELPER_ID = "longitude-helper";
const ADDRESS_HELPER_ID = "address-helper";
const ADDRESS_COUNTER_ID = "address-counter";
const ADDRESS_ERROR_ID = "address-error";
const MESSAGE_HELPER_ID = "message-helper";
const MESSAGE_COUNTER_ID = "message-counter";
const MESSAGE_ERROR_ID = "message-error";
const COORDINATE_ERROR_ID = "coordinate-error";

type RequiredTextField = "city" | "district" | "address" | "message";
type FieldErrors = Partial<Record<RequiredTextField, string>>;

export function CitizenPage() {
  const navigate = useNavigate();
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [address, setAddress] = useState("");
  const [message, setMessage] = useState("");
  const [trackingOpen, setTrackingOpen] = useState(false);
  const [trackingRequestId, setTrackingRequestId] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [coordinateError, setCoordinateError] = useState<string | null>(null);
  const mutation = useMutation({ mutationFn: createRequest });
  const cityDescription = describedBy(CITY_HELPER_ID, fieldErrors.city ? CITY_ERROR_ID : undefined);
  const districtDescription = describedBy(DISTRICT_HELPER_ID, fieldErrors.district ? DISTRICT_ERROR_ID : undefined);
  const latitudeDescription = describedBy(LATITUDE_HELPER_ID, coordinateError ? COORDINATE_ERROR_ID : undefined);
  const longitudeDescription = describedBy(LONGITUDE_HELPER_ID, coordinateError ? COORDINATE_ERROR_ID : undefined);
  const addressDescription = describedBy(ADDRESS_HELPER_ID, ADDRESS_COUNTER_ID, fieldErrors.address ? ADDRESS_ERROR_ID : undefined);
  const messageDescription = describedBy(MESSAGE_HELPER_ID, MESSAGE_COUNTER_ID, fieldErrors.message ? MESSAGE_ERROR_ID : undefined);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmedValues = {
      city: city.trim(),
      district: district.trim(),
      address: address.trim(),
      message: message.trim()
    };
    const nextFieldErrors = validateRequiredFields(trimmedValues);
    setFieldErrors(nextFieldErrors);
    if (Object.keys(nextFieldErrors).length > 0) return;

    const latitudeValue = parseOptionalCoordinate(latitude);
    const longitudeValue = parseOptionalCoordinate(longitude);
    if ((latitudeValue === undefined) !== (longitudeValue === undefined)) {
      setCoordinateError("Enlem ve boylam birlikte girilmelidir.");
      return;
    }
    setCoordinateError(null);
    const payload: CreateRequestPayload = {
      city: trimmedValues.city,
      district: trimmedValues.district,
      address: trimmedValues.address,
      latitude: latitudeValue,
      longitude: longitudeValue,
      message: trimmedValues.message
    };
    mutation.mutate(payload);
  }

  function submitTracking(event: FormEvent) {
    event.preventDefault();
    const requestId = trackingRequestId.trim();
    if (!requestId) return;
    navigate(`/status/${encodeURIComponent(requestId)}`);
  }

  return (
    <main className="page narrow">
      <header className="hero">
        <p className="eyebrow">DISASTER Cloud Platform</p>
        <h1>Yardım talebi oluştur</h1>
        <p>Durumunuzu kendi cümlelerinizle yazın.</p>
      </header>
      {mutation.data ? (
        <section className="panel success-panel">
          <h2>Talebiniz kaydedildi</h2>
          <code className="request-code">{mutation.data.requestId}</code>
          <div className="actions">
            <Link className="button" to={`/status/${mutation.data.requestId}`}>Talebi takip et</Link>
            <button className="button secondary" onClick={() => mutation.reset()}>Yeni talep</button>
          </div>
        </section>
      ) : (
        <>
          <form className="panel form-grid" onSubmit={submit}>
            <div className="field">
              <label className="field-label" htmlFor="city">
                Şehir<RequiredFieldIndicator />
              </label>
              <input id="city" value={city} onChange={e => { setCity(e.target.value); clearFieldError("city", fieldErrors, setFieldErrors); }} required minLength={CITY_MIN_LENGTH} maxLength={CITY_MAX_LENGTH} placeholder="Hatay" aria-describedby={cityDescription} aria-invalid={fieldErrors.city ? true : undefined} />
              <p id={CITY_HELPER_ID} className="field-helper">Örn. Hatay — Zorunlu, en fazla {CITY_MAX_LENGTH} karakter.</p>
              {fieldErrors.city && <p id={CITY_ERROR_ID} className="field-error" role="alert">{fieldErrors.city}</p>}
            </div>
            <div className="field">
              <label className="field-label" htmlFor="district">
                İlçe<RequiredFieldIndicator />
              </label>
              <input id="district" value={district} onChange={e => { setDistrict(e.target.value); clearFieldError("district", fieldErrors, setFieldErrors); }} required minLength={DISTRICT_MIN_LENGTH} maxLength={DISTRICT_MAX_LENGTH} placeholder="Antakya" aria-describedby={districtDescription} aria-invalid={fieldErrors.district ? true : undefined} />
              <p id={DISTRICT_HELPER_ID} className="field-helper">Örn. Antakya — Zorunlu, en fazla {DISTRICT_MAX_LENGTH} karakter.</p>
              {fieldErrors.district && <p id={DISTRICT_ERROR_ID} className="field-error" role="alert">{fieldErrors.district}</p>}
            </div>
            <div className="two-column">
              <div className="field">
                <label className="field-label" htmlFor="latitude">Enlem</label>
                <input id="latitude" value={latitude} onChange={e => { setLatitude(e.target.value); setCoordinateError(null); }} type="number" step="any" min={LATITUDE_MIN} max={LATITUDE_MAX} placeholder="36.2021" aria-describedby={latitudeDescription} aria-invalid={coordinateError ? true : undefined} />
                <p id={LATITUDE_HELPER_ID} className="field-helper">Örn. 36.2021 — İsteğe bağlı, {LATITUDE_MIN} ile {LATITUDE_MAX} arasında.</p>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="longitude">Boylam</label>
                <input id="longitude" value={longitude} onChange={e => { setLongitude(e.target.value); setCoordinateError(null); }} type="number" step="any" min={LONGITUDE_MIN} max={LONGITUDE_MAX} placeholder="36.1604" aria-describedby={longitudeDescription} aria-invalid={coordinateError ? true : undefined} />
                <p id={LONGITUDE_HELPER_ID} className="field-helper">Örn. 36.1604 — İsteğe bağlı, {LONGITUDE_MIN} ile {LONGITUDE_MAX} arasında.</p>
              </div>
            </div>
            {coordinateError && <p id={COORDINATE_ERROR_ID} className="error-box" role="alert">{coordinateError}</p>}
            <div className="field">
              <label className="field-label" htmlFor="address">
                Adres<RequiredFieldIndicator />
              </label>
              <textarea id="address" value={address} onChange={e => { setAddress(e.target.value); clearFieldError("address", fieldErrors, setFieldErrors); }} rows={3} required minLength={ADDRESS_MIN_LENGTH} maxLength={ADDRESS_MAX_LENGTH} placeholder="Örn. Atatürk Caddesi, No: 15, Antakya/Hatay" aria-describedby={addressDescription} aria-invalid={fieldErrors.address ? true : undefined} />
              <div className="field-footer">
                <p id={ADDRESS_HELPER_ID} className="field-helper">Örn. Atatürk Caddesi, No: 15, Antakya/Hatay — Zorunlu, en az {ADDRESS_MIN_LENGTH} ve en fazla {ADDRESS_MAX_LENGTH} karakter.</p>
                <span id={ADDRESS_COUNTER_ID} className="character-counter" aria-live="polite" aria-atomic="true">{address.length}/{ADDRESS_MAX_LENGTH}</span>
              </div>
              {fieldErrors.address && <p id={ADDRESS_ERROR_ID} className="field-error" role="alert">{fieldErrors.address}</p>}
            </div>
            <div className="field">
              <label className="field-label" htmlFor="message">
                Yardım Talebi<RequiredFieldIndicator />
              </label>
              <textarea id="message" value={message} onChange={e => { setMessage(e.target.value); clearFieldError("message", fieldErrors, setFieldErrors); }} rows={8} minLength={MESSAGE_MIN_LENGTH} maxLength={MESSAGE_MAX_LENGTH} required placeholder="25 kişiyiz. İçme suyumuz bitti. 2 yaralı var." aria-describedby={messageDescription} aria-invalid={fieldErrors.message ? true : undefined} />
              <div className="field-footer">
                <p id={MESSAGE_HELPER_ID} className="field-helper">Yaşadığınız durumu açıkça yazın. Zorunlu, en az {MESSAGE_MIN_LENGTH} ve en fazla {MESSAGE_MAX_LENGTH} karakter.</p>
                <span id={MESSAGE_COUNTER_ID} className="character-counter" aria-live="polite" aria-atomic="true">{message.length}/{MESSAGE_MAX_LENGTH}</span>
              </div>
              {fieldErrors.message && <p id={MESSAGE_ERROR_ID} className="field-error" role="alert">{fieldErrors.message}</p>}
            </div>
            {mutation.error && <p className="error-box">{mutation.error.message}</p>}
            <div className="actions">
              <button className="button" disabled={mutation.isPending}>{mutation.isPending ? "Gönderiliyor…" : "Talebi gönder"}</button>
              <button className="button secondary" type="button" onClick={() => setTrackingOpen(true)}>Talebi takip et</button>
            </div>
          </form>
          {!mutation.data && trackingOpen && (
            <form className="panel form-grid" onSubmit={submitTracking}>
              <div className="field">
                <label className="field-label" htmlFor="tracking-request-id">Talep ID / Takip numarası</label>
                <input id="tracking-request-id" value={trackingRequestId} onChange={e => setTrackingRequestId(e.target.value)} />
                <p className="field-helper">Talep oluşturulduktan sonra verilen takip numarasını girin.</p>
              </div>
              <div className="actions">
                <button className="button" type="submit">Talebi görüntüle</button>
              </div>
            </form>
          )}
        </>
      )}
      <p className="admin-link"><Link to="/admin/login">Kriz merkezi yetkili girişi</Link></p>
    </main>
  );
}

function validateRequiredFields(values: Record<RequiredTextField, string>): FieldErrors {
  const errors: FieldErrors = {};
  const cityError = validateTextField(values.city, "Şehir", CITY_MIN_LENGTH, CITY_MAX_LENGTH);
  const districtError = validateTextField(values.district, "İlçe", DISTRICT_MIN_LENGTH, DISTRICT_MAX_LENGTH);
  const addressError = validateTextField(values.address, "Adres", ADDRESS_MIN_LENGTH, ADDRESS_MAX_LENGTH);
  const messageError = validateTextField(values.message, "Yardım talebi", MESSAGE_MIN_LENGTH, MESSAGE_MAX_LENGTH);

  if (cityError) errors.city = cityError;
  if (districtError) errors.district = districtError;
  if (addressError) errors.address = addressError;
  if (messageError) errors.message = messageError;
  return errors;
}

function validateTextField(value: string, label: string, minLength: number, maxLength: number): string | null {
  if (value.length === 0) return `${label} zorunludur.`;
  if (value.length < minLength) return `${label} en az ${minLength} karakter olmalıdır.`;
  if (value.length > maxLength) return `${label} en fazla ${maxLength} karakter olabilir.`;
  return null;
}

function clearFieldError(
  field: RequiredTextField,
  errors: FieldErrors,
  setErrors: (value: FieldErrors) => void
) {
  if (!errors[field]) return;
  const nextErrors = { ...errors };
  delete nextErrors[field];
  setErrors(nextErrors);
}

function describedBy(...ids: Array<string | undefined>): string {
  return ids.filter((id): id is string => Boolean(id)).join(" ");
}

function RequiredFieldIndicator() {
  return (
    <>
      <span className="required-marker" aria-hidden="true">*</span>
      <span className="sr-only"> zorunlu</span>
    </>
  );
}

function parseOptionalCoordinate(value: string): number | undefined {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : undefined;
}
