from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "backend" / "knowledge_base"
FORMS = KB / "forms"
FORMS.mkdir(parents=True, exist_ok=True)

HI_NAME = "\u092a\u0942\u0930\u093e \u0928\u093e\u092e"
KN_NAME = "\u0caa\u0cc2\u0cb0\u0ccd\u0ca3 \u0cb9\u0cc6\u0cb8\u0cb0\u0cc1"
HI_DOB = "\u091c\u0928\u094d\u092e \u0924\u093f\u0925\u093f"
KN_DOB = "\u0c9c\u0ca8\u0ccd\u0cae \u0ca6\u0cbf\u0ca8\u0cbe\u0c82\u0c95"
HI_ADDR = "\u092a\u0924\u093e"
KN_ADDR = "\u0cb5\u0cbf\u0cb3\u0cbe\u0cb8"
HI_OCC = "\u0935\u094d\u092f\u0935\u0938\u093e\u092f"
KN_OCC = "\u0cb5\u0cc3\u0ca4\u0ccd\u0ca4\u0cbf"
HI_SIG = "\u0939\u0938\u094d\u0924\u093e\u0915\u094d\u0937\u0930"
KN_SIG = "\u0cb8\u0cb9\u0cbf"


def t(en: str, hi: str, kn: str) -> dict[str, str]:
    return {"en": en, "hi": hi, "kn": kn}


def field(field_id: str, aliases: list[str], ftype: str, what, why, example: str, validation: dict | None = None) -> dict:
    return {
        "field_id": field_id,
        "aliases": aliases,
        "type": ftype,
        "what_to_enter": what,
        "why_needed": why,
        "example": example,
        "validation": validation or {"kind": "non_empty"},
        "source_reference": "Synthetic demo guidance",
    }


name_what = t(
    "Enter your full legal name as printed on the identity document the form asks for.",
    "Jo pehchan patra form maangta hai, usi par chhapa poora kanooni naam likhen.",
    "Form keluva gurutina dakhalealli iruva poorna kanoonu hesaranu baredi.",
)
name_why = t(
    "The form uses this to identify the applicant.",
    "Form aavedak ki pehchan ke liye yeh naam maangta hai.",
    "Arjidaarana gurutisalu ee hesaru beku.",
)
dob_what = t(
    "Enter your date of birth in DD/MM/YYYY format.",
    "Apni janm tithi DD/MM/YYYY praroop mein likhen.",
    "Nimma janma dinankavannu DD/MM/YYYY svaroopadalli baredi.",
)
addr_what = t(
    "Enter the full postal address the form asks for, including house number and locality.",
    "Ghar sankhya aur ilake ke saath poora daak pata likhen.",
    "Mane sankhye mattu pradesha sahita poornadaak vilasavannu baredi.",
)
occ_what = t(
    "Enter your current occupation or write Student, Homemaker, or Retired if that applies.",
    "Apna vartaman vyavsay likhen, ya Student / Homemaker / Retired likhen.",
    "Nimma igina vrttiyannu baredi, athava Student / Homemaker / Retired baredi.",
)
nom_what = t(
    "Enter the full name of the person you want to name as nominee, if the form asks for one.",
    "Yadi form maange to nominee ke roop mein jis vyakti ka naam dena chahte hain, unka poora naam likhen.",
    "Form kelidare nominee aagi hesaru needabekada vyaktiya poorna hesaranu baredi.",
)
sig_what = t(
    "Leave this blank in FormSathi. Sign the official paper form by hand.",
    "Yahan FormSathi mein kuch na likhen. Asli form par haath se hastakshar karen.",
    "FormSathiyalli idannu khali bidi. Adhikrita formnalli kaiyinda sahi maadi.",
)

common = [
    {
        "id": "full_name",
        "aliases": ["full name", "name of applicant", "applicant name", "name"],
        "type": "text",
        "simple_label": t("Full name", HI_NAME, KN_NAME),
        "what_to_enter": name_what,
        "why_needed": name_why,
        "example": "Ananya Rao",
        "format_hint": "Given name and family name",
    },
    {
        "id": "date_of_birth",
        "aliases": ["date of birth", "dob", "birth date"],
        "type": "date",
        "simple_label": t("Date of birth", HI_DOB, KN_DOB),
        "what_to_enter": dob_what,
        "example": "15/08/1998",
        "format_hint": "DD/MM/YYYY",
    },
    {
        "id": "address",
        "aliases": ["address", "residential address", "postal address"],
        "type": "multiline",
        "simple_label": t("Address", HI_ADDR, KN_ADDR),
        "what_to_enter": addr_what,
        "example": "12 Lotus Lane, Demo Nagar, Bengaluru 560001",
    },
    {
        "id": "occupation",
        "aliases": ["occupation", "profession", "employment"],
        "type": "text",
        "simple_label": t("Occupation", HI_OCC, KN_OCC),
        "what_to_enter": occ_what,
        "example": "School teacher",
    },
    {
        "id": "nominee",
        "aliases": ["nominee", "nominee name"],
        "type": "text",
        "simple_label": t("Nominee", "Nominee", "Nominee"),
        "what_to_enter": nom_what,
        "why_needed": t(
            "A nominee is the person named to receive proceeds if the account holder dies. This is general guidance, not legal advice.",
            "Nominee vah vyakti hai jiska naam aap aapatkal ke liye dete hain. Yeh kanooni salah nahi hai.",
            "Nominee endare khateya malika illadiddare hesaru kottiruva vyakti. Idu kanoonu salahe alla.",
        ),
        "example": "Rohit Sharma",
    },
    {
        "id": "signature",
        "aliases": ["signature", "applicant signature", "sign here"],
        "type": "signature",
        "simple_label": t("Signature", HI_SIG, KN_SIG),
        "what_to_enter": sig_what,
        "example": "[SIGN MANUALLY]",
    },
]

forms = [
    {
        "form_id": "demo_bank_account_opening_v1",
        "display_name": "Demo Bank Account Opening Form",
        "category": "banking",
        "version": "1",
        "disclaimer": "Synthetic demonstration form, not an official bank document.",
        "fingerprint_terms": ["account type", "nominee", "occupation", "demo bank"],
        "fields": [
            field("full_name", ["name of applicant", "applicant name", "full name"], "text", name_what, name_why, "Ananya Rao"),
            field("date_of_birth", ["date of birth", "dob"], "date", dob_what, t("The bank uses this as part of customer identification on this demo form.", "Yeh demo form par pehchan ke liye janm tithi maangi gayi hai.", "Ee demo formnalli gurutige janma dinanka kelalagide."), "15/08/1998", {"kind": "date", "format": "DD/MM/YYYY"}),
            field("occupation", ["occupation"], "text", occ_what, t("The form records how the applicant earns a living.", "Form aavedak ke vyavsay ka record rakhta hai.", "Arjidaara vrttiya dakhale idu."), "School teacher"),
            field("nominee", ["nominee", "nominee name"], "text", nom_what, common[4]["why_needed"], "Rohit Sharma"),
            field("account_type", ["account type", "savings", "current"], "checkbox", t("Mark the account type printed on the form, such as Savings or Current.", "Form par chhape Savings ya Current account type ko chinhit karen.", "Formnalli iruva Savings athava Current khateya prakara gurutisi."), t("The demo bank groups applications by account type.", "Demo bank account prakar se aavedan jodta hai.", "Demo bank khateya prakara arjigala gumpumaaduttade."), "Savings"),
            field("address", ["residential address", "address"], "multiline", addr_what, t("The bank uses a postal address for this demo application.", "Yeh demo aavedan ke liye daak pata maanga gaya hai.", "Ee demo arjige daak vilasa beku."), "12 Lotus Lane, Demo Nagar"),
            field("signature", ["applicant signature", "signature", "sign here"], "signature", sig_what, t("A signature confirms the applicant reviewed the official form.", "Hastakshar se aavedak form padhkar sahmat hota hai.", "Sahi arjidaaru form nodiddu dhrudhapadisuttade."), "[SIGN MANUALLY]"),
        ],
    },
    {
        "form_id": "demo_scholarship_application_v1",
        "display_name": "Demo Scholarship Application Form",
        "category": "education",
        "version": "1",
        "disclaimer": "Synthetic demonstration form, not an official scholarship document.",
        "fingerprint_terms": ["scholarship", "course name", "institution", "marks"],
        "fields": [
            field("full_name", ["student name", "full name", "name of applicant"], "text", name_what, t("The office uses this to identify the student.", "Chatra ki pehchan ke liye naam maanga gaya hai.", "Vidyarthiya gurutige hesaru beku."), "Meera Iyer"),
            field("date_of_birth", ["date of birth"], "date", dob_what, t("Age or eligibility checks may use this date. Verify official rules.", "Aayu jaanch ke liye tithi ho sakti hai. Adhikarik niyam dekhen.", "Vayassina padyarigagi dinanka beku. Adhikrita niyamagala parishilisi."), "03/11/2004", {"kind": "date", "format": "DD/MM/YYYY"}),
            field("institution", ["institution", "college name", "school name"], "text", t("Enter the name of the school or college printed on your ID card.", "Apne ID card par chhapa school ya college ka naam likhen.", "Nimma ID cardnalli iruva shaale athava kalejiya hesaru baredi."), t("The form routes the application to an institution.", "Aavedan sanstha tak pahunchane ke liye.", "Arjiyannu sansthege kaluhisalu."), "Demo Public College"),
            field("course_name", ["course name", "programme"], "text", t("Enter the course or programme name you are applying from.", "Jis course se aavedan kar rahe hain uska naam likhen.", "Neevu arji maaduttiruva pathyakramada hesaru baredi."), t("The scholarship office groups applications by course.", "Course ke anusaar aavedan jode jaate hain.", "Pathyakramada prakara arjigala gumpumaaduttare."), "B.Sc. Computer Science"),
            field("marks", ["marks obtained", "percentage"], "text", t("Enter marks or percentage exactly as on the mark sheet.", "Marksheet jaisi sankhya likhen.", "Ankapatradalli iruva pramanakke sariyagi anka baredi."), t("This demo form uses marks to rank applications.", "Yeh demo form ankdon se kram nikalta hai.", "Ee demo form ankadinda sariyaadisuttade."), "86.5"),
            field("declaration", ["declaration", "i confirm"], "checkbox", t("Mark the box only if you agree with the printed declaration.", "Tabhi box chinhit karen jab aap chhape ghoshna se sahmat hon.", "Mudrisida ghoshanege sammatadiddare maatra gurutisi."), t("Records that the student reviewed the statement.", "Chatra ne kathan padha yeh darj karta hai.", "Vidyarthi helikeya nodida dakhale."), "I confirm"),
            field("signature", ["student signature", "signature"], "signature", sig_what, t("Sign the official paper after checking every answer.", "Har uttar jaanchkar asli kagaz par hastakshar karen.", "Prati uttara parishilisi adhikrita kaagadadalli sahi maadi."), "[SIGN MANUALLY]"),
        ],
    },
    {
        "form_id": "demo_insurance_nominee_v1",
        "display_name": "Demo Insurance Nominee Form",
        "category": "insurance",
        "version": "1",
        "disclaimer": "Synthetic demonstration form, not an official insurance document.",
        "fingerprint_terms": ["policy number", "nominee", "relationship", "share percent"],
        "fields": [
            field("policyholder_name", ["policyholder name", "full name", "name of applicant"], "text", name_what, t("Identifies the person named on the demo policy.", "Demo policy par naam ke liye.", "Demo policynalli hesaru gurutisalu."), "Kavya Menon"),
            field("policy_number", ["policy number"], "text", t("Copy the policy number exactly as printed on the policy schedule.", "Policy schedule par chhapa number vaise hi likhen.", "Policy schedulealli iruva numberannu nijavagiyu baredi."), t("The office matches this form to a policy record.", "Form ko policy se jodne ke liye.", "Formannu policy dakhalege sariyaadisalu."), "DEMO-INS-4421"),
            field("nominee", ["nominee name", "nominee"], "text", nom_what, common[4]["why_needed"], "Arjun Menon"),
            field("relationship", ["relationship"], "text", t("Enter the relationship printed on the options, such as Spouse or Parent.", "Spouse ya Parent jaise chhape vikalp mein se sambandh likhen.", "Spouse athava Parent haage mudrisida sambandha baredi."), t("The form records how the nominee is related.", "Nominee ka rishta darj karne ke liye.", "Nominee sambandha dakhalege."), "Spouse"),
            field("share_percent", ["share percent", "share %"], "text", t("Enter the share percentage the form asks for, using numbers only.", "Jo hisse ki pratishat form maange, keval ank likhen.", "Form keluva palada pratisatavannu sankhyegala maatra baredi."), t("Some demo forms split a benefit across nominees.", "Kuch demo form hisse baantte hain.", "Kela demo formgalu palavannu hanchuttave."), "100"),
            field("date_of_birth", ["date of birth"], "date", dob_what, t("Used on this demo form as a nominee identifier.", "Yeh demo form par nominee pehchan ke liye.", "Ee demo formnalli nominee gurutige."), "21/04/1995", {"kind": "date", "format": "DD/MM/YYYY"}),
            field("signature", ["signature", "sign here"], "signature", sig_what, t("A handwritten signature belongs only on the official paper.", "Hastakshar sirf asli kagaz par likhen.", "Sahi kevala adhikrita kaagadadalli."), "[SIGN MANUALLY]"),
        ],
    },
    {
        "form_id": "demo_government_service_v1",
        "display_name": "Demo Basic Government Service Application",
        "category": "government",
        "version": "1",
        "disclaimer": "Synthetic demonstration form, not an official government document.",
        "fingerprint_terms": ["service requested", "ward number", "acknowledgement", "demo civic"],
        "fields": [
            field("full_name", ["applicant name", "full name"], "text", name_what, t("The civic office uses this to identify the applicant.", "Nagar karyalay aavedak ko pehchanne ke liye.", "Nagara karyalaya arjidaarana gurutisalu."), "Farhan Qureshi"),
            field("address", ["address", "residential address"], "multiline", addr_what, t("The office may visit or post a reply to this address.", "Is pata par uttar bheja ja sakta hai.", "Ee vilasakke uttara kaluhisabahudu."), "44 Demo Ward Street"),
            field("ward_number", ["ward number"], "text", t("Enter the ward or locality number printed on your civic record, if you have it.", "Yadi pata ho to civic record ka ward number likhen.", "Civic dakhale iruvaga ward sankhye baredi."), t("Helps route a local service request.", "Sthaniya seva ke routing ke liye.", "Sthaliya sevege kaluhisalu."), "12"),
            field("service_requested", ["service requested", "type of service"], "radio", t("Choose the printed service you are requesting, such as Water or Street light.", "Water ya Street light jaise chhape seva vikalp chunen.", "Water athava Street light haage mudrisida seveyannu aayisi."), t("Tells the office which demo service is needed.", "Kaunsi seva chahiye yeh batata hai.", "Yava seve beku embudannu heluttade."), "Water"),
            field("contact_number", ["mobile number", "contact number"], "text", t("Enter a 10-digit mobile number you can be reached on.", "10 ank ka mobile number likhen.", "10 ankada mobile number baredi."), t("The office may call about this demo request.", "Is demo aavedan par call ho sakta hai.", "Ee demo arji bagge call agabahudu."), "9876543210"),
            field("acknowledgement", ["acknowledgement", "i understand"], "checkbox", t("Mark only if you understand that this is a demonstration form.", "Tabhi chinhit karen jab aap samajhte hain ki yeh pradarshan form hai.", "Idu pradarshana form endu tilididdare maatra gurutisi."), t("Confirms the applicant read the printed notice.", "Aavedak ne suchna padhi yeh darj karta hai.", "Arjidaaru suchane nodida dakhale."), "I understand"),
            field("signature", ["applicant signature", "signature"], "signature", sig_what, t("Sign the official copy after you verify every answer.", "Har uttar jaanchkar asli prati par hastakshar karen.", "Prati uttara parishilisi adhikrita pratiyalli sahi maadi."), "[SIGN MANUALLY]"),
        ],
    },
]


def main() -> None:
    (KB / "common_fields.json").write_text(json.dumps(common, ensure_ascii=False, indent=2), encoding="utf-8")
    for form in forms:
        (FORMS / f"{form['form_id']}.json").write_text(json.dumps(form, ensure_ascii=False, indent=2), encoding="utf-8")
    (KB / "README.md").write_text(
        "# FormSathi knowledge base\n\n"
        "Synthetic demonstration guidance only. Not official government, bank, insurer, or school instructions.\n"
        "Chunking is one field per language. Seed with `python scripts/seed_knowledge_base.py`.\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(forms)} forms and common_fields.json")


if __name__ == "__main__":
    main()
