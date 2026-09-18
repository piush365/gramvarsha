import { CorrectedForecast } from "./downscale";

export type Crop = "sugarcane" | "grapes" | "jowar" | "soybean" | "turmeric";
export type CropStage = "sowing" | "vegetative" | "flowering" | "maturity";
export type Lang = "en" | "mr";

export const CROPS: { id: Crop; label: string }[] = [
  { id: "sugarcane", label: "Sugarcane" },
  { id: "grapes", label: "Grapes" },
  { id: "jowar", label: "Jowar (Sorghum)" },
  { id: "soybean", label: "Soybean" },
  { id: "turmeric", label: "Turmeric" },
];

export const STAGES: { id: CropStage; label: string }[] = [
  { id: "sowing", label: "Sowing" },
  { id: "vegetative", label: "Vegetative" },
  { id: "flowering", label: "Flowering" },
  { id: "maturity", label: "Maturity" },
];

export type Advisory = {
  riskLevel: "low" | "moderate" | "high";
  en: { summary: string; actions: string[] };
  mr: { summary: string; actions: string[] };
};

export function generateAdvisory(f: CorrectedForecast, crop: Crop, stage: CropStage): Advisory {
  const actionsEn: string[] = [];
  const actionsMr: string[] = [];
  let riskLevel: "low" | "moderate" | "high" = "low";

  if (f.rainfallMm > 40) {
    riskLevel = "high";
    actionsEn.push("Heavy rain expected — clear field drains and delay any pesticide spraying.");
    actionsMr.push("जोरदार पाऊस अपेक्षित — शेतातील पाणी निचरा मार्ग मोकळे करा आणि कीटकनाशक फवारणी पुढे ढकला.");
  } else if (f.rainfallMm > 15) {
    riskLevel = "moderate";
    actionsEn.push("Moderate rain likely — postpone irrigation for 1–2 days.");
    actionsMr.push("मध्यम पाऊस शक्य — सिंचन १-२ दिवस पुढे ढकला.");
  } else {
    actionsEn.push("Low rain expected — irrigate as per your normal schedule.");
    actionsMr.push("कमी पाऊस अपेक्षित — नेहमीप्रमाणे सिंचन वेळापत्रकानुसार करा.");
  }

  if (f.tempMaxC > 36) {
    riskLevel = riskLevel === "high" ? "high" : "moderate";
    actionsEn.push("High daytime heat — irrigate early morning or evening to reduce crop stress.");
    actionsMr.push("जास्त तापमान — पिकावरील ताण कमी करण्यासाठी सकाळी लवकर किंवा संध्याकाळी सिंचन करा.");
  }

  if (crop === "sugarcane" && stage === "flowering" && f.rainfallMm > 15) {
    actionsEn.push("Flowering-stage sugarcane is sensitive to waterlogging — check drainage in low-lying plots.");
    actionsMr.push("फुलोऱ्यातील ऊस पाणी साचण्यास संवेदनशील असतो — सखल भागातील निचरा तपासा.");
  }
  if (crop === "grapes" && f.humidityPct > 70) {
    riskLevel = "high";
    actionsEn.push("High humidity raises downy mildew risk in grapes — inspect the canopy and consider a preventive spray.");
    actionsMr.push("जास्त आर्द्रतेमुळे द्राक्षांमध्ये डाउनी मिल्ड्यूचा धोका वाढतो — पानसंभार तपासा आणि प्रतिबंधात्मक फवारणीचा विचार करा.");
  }
  if (crop === "jowar" && stage === "sowing" && f.rainfallMm < 10) {
    actionsEn.push("Low rain at sowing stage — ensure pre-sowing irrigation before broadcasting seed.");
    actionsMr.push("पेरणीच्या वेळी कमी पाऊस — बियाणे पेरण्यापूर्वी पूर्व-सिंचन सुनिश्चित करा.");
  }
  if (crop === "soybean" && f.humidityPct > 75) {
    actionsEn.push("Prolonged humidity favors leaf-spot in soybean — monitor the lower canopy leaves.");
    actionsMr.push("सतत आर्द्रतेमुळे सोयाबीनमध्ये पानावरील ठिपके वाढू शकतात — खालच्या पानांवर लक्ष ठेवा.");
  }
  if (crop === "turmeric" && f.rainfallMm > 30) {
    actionsEn.push("Excess rain risks rhizome rot in turmeric — raise bed drainage wherever water pools.");
    actionsMr.push("अतिरिक्त पावसामुळे हळदीत कंद कुजण्याचा धोका — पाणी साचणाऱ्या ठिकाणी गादी वाफ्याचा निचरा वाढवा.");
  }

  const riskLabelEn = riskLevel === "high" ? "High-risk" : riskLevel === "moderate" ? "Moderate-risk" : "Low-risk";
  const riskLabelMr = riskLevel === "high" ? "उच्च-धोका" : riskLevel === "moderate" ? "मध्यम-धोका" : "कमी-धोका";

  return {
    riskLevel,
    en: {
      summary: `${riskLabelEn} day for ${crop} at ${stage} stage — ${f.rainfallMm} mm rain, ${f.tempMaxC}°C max.`,
      actions: actionsEn,
    },
    mr: {
      summary: `${crop} (${stage} अवस्था) साठी ${riskLabelMr} दिवस — ${f.rainfallMm} मिमी पाऊस, ${f.tempMaxC}°C कमाल तापमान.`,
      actions: actionsMr,
    },
  };
}
