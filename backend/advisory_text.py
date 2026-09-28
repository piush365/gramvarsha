"""Hand-written advisory text in English, Hindi and Marathi.

Rules in advisory.py decide WHICH messages apply; this file only holds the words.
Each alert has a full line (WhatsApp / voice) and a short line (SMS).
Placeholders: {rain} mm, {tmax} °C, {rh} %, {wind} km/h, {when} (today/tomorrow),
{rain5} (5-day rain total). Numbers are always inserted by code, never written here.

Language notes: simple spoken rural Marathi/Hindi, the words farmers use
(केवडा for downy mildew, तेलकट डाग for oily spot), no transliterated English.
"""

LANGS = ("en", "hi", "mr")

CROPS = {
    "sugarcane":   {"en": "Sugarcane",   "hi": "गन्ना",    "mr": "ऊस"},
    "grapes":      {"en": "Grapes",      "hi": "अंगूर",    "mr": "द्राक्ष"},
    "turmeric":    {"en": "Turmeric",    "hi": "हल्दी",    "mr": "हळद"},
    "soybean":     {"en": "Soybean",     "hi": "सोयाबीन",  "mr": "सोयाबीन"},
    "jowar":       {"en": "Jowar",       "hi": "ज्वार",     "mr": "ज्वारी"},
    "wheat":       {"en": "Wheat",       "hi": "गेहूं",     "mr": "गहू"},
    "onion":       {"en": "Onion",       "hi": "प्याज",    "mr": "कांदा"},
    "pomegranate": {"en": "Pomegranate", "hi": "अनार",     "mr": "डाळिंब"},
}

STAGES = {
    "sowing":     {"en": "sowing",            "hi": "बुवाई",          "mr": "पेरणी"},
    "vegetative": {"en": "growth stage",      "hi": "बढ़वार",          "mr": "वाढीची अवस्था"},
    "flowering":  {"en": "flowering",         "hi": "फूल आना",        "mr": "फुलोरा"},
    "fruiting":   {"en": "fruiting/maturity", "hi": "फल/दाना भरना",   "mr": "फळधारणा/पक्वता"},
    "harvest":    {"en": "harvest",           "hi": "कटाई",           "mr": "काढणी"},
}

WHEN = {
    "today":    {"en": "today",    "hi": "आज", "mr": "आज"},
    "tomorrow": {"en": "tomorrow", "hi": "कल", "mr": "उद्या"},
}

ALERTS = {
    "HEAT": {
        "en": ("Very hot, {tmax}°C. Give light, frequent irrigation, cover the soil with mulch and keep animals in shade.",
               "Heat {tmax}C: light frequent irrigation, mulch"),
        "hi": ("बहुत गर्मी, {tmax}°से. थोड़ा-थोड़ा बार-बार पानी दें, मिट्टी पर पलवार बिछाएं और पशुओं को छाया में रखें.",
               "गर्मी {tmax}°से: थोड़ा-थोड़ा बार-बार पानी दें"),
        "mr": ("खूप उष्णता, {tmax}°से. थोडे थोडे पण वारंवार पाणी द्या, जमिनीवर आच्छादन करा आणि जनावरे सावलीत ठेवा.",
               "उष्णता {tmax}°से: थोडे थोडे वारंवार पाणी द्या"),
    },
    "HEAVY_RAIN": {
        "en": ("Heavy rain of {rain} mm expected {when}. Do not spray or apply fertilizer for the next 48 hours.",
               "Rain {rain}mm {when}: no spraying or fertilizer for 48h"),
        "hi": ("{when} {rain} मिमी तेज़ बारिश की संभावना. अगले 48 घंटे छिड़काव न करें और खाद न डालें.",
               "{when} {rain}मिमी बारिश: 48 घंटे छिड़काव-खाद नहीं"),
        "mr": ("{when} {rain} मिमी जोराचा पाऊस अपेक्षित. पुढचे 48 तास फवारणी करू नका आणि खत देऊ नका.",
               "{when} {rain}मिमी पाऊस: 48 तास फवारणी-खत नको"),
    },
    "HARVEST_RAIN": {
        "en": ("Rain of {rain} mm {when}. Delay harvest if you can, and keep harvested produce covered.",
               "Rain {when}: delay harvest, cover produce"),
        "hi": ("{when} {rain} मिमी बारिश. हो सके तो कटाई टालें और कटी फसल ढककर रखें.",
               "{when} बारिश: कटाई टालें, फसल ढकें"),
        "mr": ("{when} {rain} मिमी पाऊस. शक्य असल्यास काढणी पुढे ढकला आणि काढलेला माल झाकून ठेवा.",
               "{when} पाऊस: काढणी थांबवा, माल झाका"),
    },
    "GRAPE_DOWNY": {
        "en": ("Grapes: humid weather spreads downy mildew. Spray a recommended fungicide once the leaves are dry and the wind is calm.",
               "Grapes: downy mildew risk, spray fungicide when leaves dry"),
        "hi": ("अंगूर: नमी वाले मौसम में डाउनी रोग फैलता है. पत्ते सूखने पर और हवा शांत होने पर सुझाई गई फफूंदनाशक दवा छिड़कें.",
               "अंगूर: डाउनी रोग का खतरा, दवा छिड़कें"),
        "mr": ("द्राक्ष: दमट हवेत केवडा रोग पसरतो. पाने कोरडी झाल्यावर आणि वारा शांत असताना शिफारस केलेले बुरशीनाशक फवारा.",
               "द्राक्ष: केवडा रोगाचा धोका, बुरशीनाशक फवारा"),
    },
    "TURMERIC_DRAIN": {
        "en": ("Turmeric: heavy rain can rot the rhizomes. Open the field drains so water does not stand.",
               "Turmeric: open drains, no standing water"),
        "hi": ("हल्दी: ज़्यादा बारिश से गांठें सड़ सकती हैं. खेत की नालियां खोल दें, पानी जमा न होने दें.",
               "हल्दी: नालियां खोलें, पानी न रुके"),
        "mr": ("हळद: जास्त पावसाने कंद कुजू शकतात. शेतातील चर मोकळे करा, पाणी साचू देऊ नका.",
               "हळद: चर मोकळे करा, पाणी साचू देऊ नका"),
    },
    "POMEGRANATE_BLIGHT": {
        "en": ("Pomegranate: warm, humid weather spreads oily spot. Remove spotted fruit and spray as recommended.",
               "Pomegranate: oily spot risk, remove spotted fruit"),
        "hi": ("अनार: नमी वाले मौसम में तेलिया रोग फैलता है. दाग वाले फल तोड़कर हटा दें और सुझाई गई दवा छिड़कें.",
               "अनार: तेलिया रोग का खतरा, दाग वाले फल हटाएं"),
        "mr": ("डाळिंब: दमट हवेत तेलकट डाग रोग वाढतो. डाग असलेली फळे काढून टाका आणि शिफारशीनुसार फवारणी करा.",
               "डाळिंब: तेलकट डागाचा धोका, डागाची फळे काढा"),
    },
    "WHEAT_HEAT": {
        "en": ("Wheat: heat during grain filling makes grains thin. Give a light irrigation in the evening.",
               "Wheat: heat at grain filling, light evening irrigation"),
        "hi": ("गेहूं: दाना भरते समय गर्मी से दाना पतला होता है. शाम को हल्की सिंचाई करें.",
               "गेहूं: गर्मी, शाम को हल्की सिंचाई करें"),
        "mr": ("गहू: दाणे भरताना उष्णतेमुळे दाणे बारीक होतात. संध्याकाळी हलके पाणी द्या.",
               "गहू: उष्णता, संध्याकाळी हलके पाणी द्या"),
    },
    "JOWAR_MOULD": {
        "en": ("Jowar: humid weather at grain stage brings grain mould. Harvest on time and dry the grain well.",
               "Jowar: grain mould risk, harvest on time"),
        "hi": ("ज्वार: दाना भरते समय नमी से बाली पर फफूंद लगती है. समय पर कटाई करें और दाने अच्छी तरह सुखाएं.",
               "ज्वार: बाली पर फफूंद का खतरा"),
        "mr": ("ज्वारी: दाणे भरताना दमट हवेमुळे कणसावर बुरशी येते. वेळेवर काढणी करा आणि दाणे चांगले वाळवा.",
               "ज्वारी: कणसावर बुरशीचा धोका"),
    },
    "FUNGAL": {
        "en": ("Humidity {rh}% during flowering: high risk of fungal disease. Check leaves and flowers every day.",
               "Humidity {rh}%: fungal risk, check crop daily"),
        "hi": ("फूल आने के समय नमी {rh}%: फफूंद रोग का खतरा ज़्यादा है. रोज़ पत्ते और फूल देखें.",
               "नमी {rh}%: फफूंद रोग का खतरा, फसल देखें"),
        "mr": ("फुलोऱ्यात हवेत ओलावा {rh}%: बुरशी रोगाचा धोका जास्त. रोज पाने आणि फुले तपासा.",
               "ओलावा {rh}%: बुरशी रोगाचा धोका, पीक तपासा"),
    },
    "IRRIGATE": {
        "en": ("Dry and hot ({tmax}°C, rain {rain} mm). Irrigate, preferably in the morning or evening.",
               "Dry, {tmax}C: irrigate morning or evening"),
        "hi": ("सूखा और गर्म मौसम ({tmax}°से, बारिश {rain} मिमी). सिंचाई करें, हो सके तो सुबह या शाम को.",
               "सूखा, {tmax}°से: सुबह या शाम सिंचाई करें"),
        "mr": ("कोरडे आणि गरम हवामान ({tmax}°से, पाऊस {rain} मिमी). पिकाला पाणी द्या, शक्यतो सकाळी किंवा संध्याकाळी.",
               "कोरडे, {tmax}°से: सकाळी किंवा संध्याकाळी पाणी द्या"),
    },
    "SOWING_DRY": {
        "en": ("Little rain ahead ({rain5} mm in 5 days). Do not sow in dry soil unless you can irrigate.",
               "Only {rain5}mm rain in 5 days: don't sow in dry soil"),
        "hi": ("अगले 5 दिन बारिश कम ({rain5} मिमी). सिंचाई की सुविधा न हो तो सूखी ज़मीन में बुवाई न करें.",
               "5 दिन में {rain5}मिमी बारिश: सूखे में बुवाई नहीं"),
        "mr": ("पुढील 5 दिवस पाऊस कमी ({rain5} मिमी). पाण्याची सोय नसेल तर कोरड्या जमिनीत पेरणी करू नका.",
               "5 दिवसांत {rain5}मिमी पाऊस: कोरड्यात पेरणी नको"),
    },
    "WIND": {
        "en": ("Wind up to {wind} km/h during the day. Spray only in the calm early morning.",
               "Wind {wind}km/h: spray only early morning"),
        "hi": ("दिन में हवा {wind} किमी/घंटा तक. छिड़काव सिर्फ़ सुबह जल्दी करें, जब हवा शांत हो.",
               "हवा {wind}किमी/घंटा: छिड़काव सिर्फ़ सुबह जल्दी"),
        "mr": ("दिवसा वारा {wind} किमी/तास पर्यंत. फवारणी फक्त सकाळी लवकर करा, वारा शांत असताना.",
               "वारा {wind}किमी/तास: फवारणी फक्त सकाळी लवकर"),
    },
    "NORMAL": {
        "en": ("No weather risk in the next 2 days. Continue routine field work.",
               "No weather risk next 2 days"),
        "hi": ("अगले 2 दिन मौसम से कोई खतरा नहीं. खेत का रोज़ का काम जारी रखें.",
               "अगले 2 दिन मौसम ठीक"),
        "mr": ("पुढील 2 दिवस हवामानाचा धोका नाही. शेतीची नेहमीची कामे सुरू ठेवा.",
               "पुढील 2 दिवस हवामान ठीक"),
    },
}

# WhatsApp message frame.
HEADER = {
    "en": "GramVarsha | {place} | {date}",
    "hi": "ग्रामवर्षा | {place} | {date}",
    "mr": "ग्रामवर्षा | {place} | {date}",
}
DAY_LINE = {
    "en": "{day}: rain {rain} mm, {tmin}-{tmax}°C, humidity {rh}%",
    "hi": "{day}: बारिश {rain} मिमी, तापमान {tmin}-{tmax}°से, नमी {rh}%",
    "mr": "{day}: पाऊस {rain} मिमी, तापमान {tmin}-{tmax}°से, ओलावा {rh}%",
}
DAY_NAME = {"en": ("Today", "Tomorrow"), "hi": ("आज", "कल"), "mr": ("आज", "उद्या")}
CROP_LINE = {"en": "{crop} ({stage}):", "hi": "{crop} ({stage}):", "mr": "{crop} ({stage}):"}
REPLY_LINE = {
    "en": "Reply 1 if the forecast was right, 2 if wrong.",
    "hi": "अनुमान सही हो तो 1, गलत हो तो 2 भेजें.",
    "mr": "अंदाज बरोबर असल्यास 1, चुकीचा असल्यास 2 पाठवा.",
}
# English SMS writes "31C", not "31°C": the degree sign is not in the GSM-7 alphabet and
# would force Unicode encoding (70 instead of 160 characters per SMS).
SMS_SIGN = {"en": " -GramVarsha", "hi": " -ग्रामवर्षा", "mr": " -ग्रामवर्षा"}

RANGE_WORD = {"en": "to", "hi": "से", "mr": "ते"}

# Spoken versions of units for the voice message (gTTS reads abbreviations badly).
VOICE_UNITS = {
    "en": [("°C", " degrees"), (" mm", " millimetres"), (" km/h", " kilometres per hour"), ("%", " percent")],
    "hi": [("°से", " डिग्री"), (" मिमी", " मिलीमीटर"), (" किमी/घंटा", " किलोमीटर प्रति घंटा"), ("%", " प्रतिशत")],
    "mr": [("°से", " अंश"), (" मिमी", " मिलिमीटर"), (" किमी/तास", " किलोमीटर प्रति तास"), ("%", " टक्के")],
}
