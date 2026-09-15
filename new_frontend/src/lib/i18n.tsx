import React, { createContext, useContext, useState, useEffect } from 'react';

export type Language = 'en' | 'hi';

export const translations = {
  en: {
    // Top Bar
    gov_india: 'Government of India',
    gov_india_hindi: 'भारत सरकार',
    ministry_title: 'Ministry of Consumer Affairs, Food & Public Distribution',
    dept_title: 'Department of Consumer Affairs',
    legal_metrology_div: 'LEGAL METROLOGY ENFORCEMENT DIVISION',
    portal_title: 'PRAMAAN',
    portal_hindi_title: 'प्रमाण',
    rules_subtitle: 'Legal Metrology (Packaged Commodities) Rules, 2011',
    gazetted_enforcement: 'GAZETTED FIELD ENFORCEMENT PORTAL',
    network_online: 'ONLINE',
    network_offline: 'OFFLINE',
    pending_sync: 'PENDING SYNC',
    inspector: 'Inspector',
    active_on_duty: 'ACTIVE ON-DUTY',
    profile_badge: 'PROFILE',
    view_profile: 'Inspector Dossier',

    // Navigation Tabs
    tab_scan: 'Live Inspection & Scan',
    tab_scan_sub: 'Real-time Optical Audit',
    tab_certificate: 'Statutory Certificate & Memo',
    tab_certificate_sub: 'Form-V / Legal Memo',
    tab_ledger: 'Inspection Case Register',
    tab_ledger_sub: 'Statutory Ledger Records',
    tab_rules: 'Legal Metrology Rules (PCR 2011)',
    tab_rules_sub: 'Statutory Gazette Library',

    // Marquee
    marquee_badge: 'GAZETTE DIRECTIVE',
    marquee_badge_hi: 'राजपत्र अधिसूचना',
    marquee_text:
      '[G.S.R. 2026/LM-ENF] The Legal Metrology (Packaged Commodities) Rules, 2011 are strictly enforced. All pre-packaged commodities must declare Manufacturer/Packer/Importer details, MRP (inclusive of all taxes), Net Quantity with standard units, Date of Manufacture, and Consumer Care details under Rule 6. Mandatory real-time field scans and cryptographic hash ledgers are legally binding under Section 15 & Section 36 of the Legal Metrology Act, 2011. National Consumer Helpline: 1915',

    // Ribbon
    ribbon_cadre: 'STATUTORY CADRE',
    ribbon_protocol: 'SECURITY PROTOCOL',
    ribbon_act: 'ACT',
    ribbon_act_val: 'Legal Metrology Act, 2011 (1 of 2010)',
    ribbon_hash: 'SEC-HASH',
    ribbon_docket_active: 'OFFICIAL DOCKET ACTIVE',
    ribbon_offline_mode: 'OFFLINE BUFFER MODE',

    // Live Scan View
    field_audit_title: 'FIELD INSPECTION RECORD',
    case_docket: 'REPORT NO.',
    commodity: 'COMMODITY',
    inspection_location: 'INSPECTION SITE',
    capture_new_label: '+ Capture / Scan New Label',
    live_dossier_title: 'Live Optical Metrology Audit & Inspection Dossier',
    deficient_breach: 'DEFICIENT (1 BREACH)',
    fully_compliant: 'FULLY COMPLIANT',
    under_review: 'NEEDS REVIEW',
    rule_summary_desc: 'Automated statutory rule compliance assessment under Legal Metrology (Packaged Commodities) Rules, 2011 & S.O. 628(E).',
    total_clauses: 'TOTAL CLAUSES',
    valid_clauses: 'VALID',
    review_clauses: 'REVIEW',
    defect_clauses: 'DEFECT',
    actionable_sec_36: 'ACTIONABLE SEC 36',
    seizure_noticeable: 'SEIZURE NOTICEABLE',
    all_rules_passed: 'STATUTORY PASS',

    // Viewport
    optical_viewport_title: 'OPTICAL EVIDENCE VIEWPORT',
    annotations_toggle: 'ANNOTATIONS',
    zoom_scale: 'SCALE',
    upload_own_image: 'Upload Packaging Image',
    scan_now_button: 'Run Optical Metrology Scan',
    scanning_in_progress: 'Scanning & analyzing package inscriptions...',

    // Inspector Dossier Side Card
    inspection_findings: 'STATUTORY INSPECTION FINDINGS',
    rule_violated: 'RULE VIOLATED',
    mandatory_requirement: 'MANDATORY STATUTORY REQUIREMENT',
    observed_detected: 'OBSERVED / EXTRACTED VALUE',
    font_geometry: 'FONT GEOMETRY & PLACEMENT',
    prescribed_penalty: 'STATUTORY ACTION / PENALTY',
    official_cadre_stamp: 'OFFICIAL CADRE STAMP',

    // Checklist
    complete_checklist: 'COMPLETE STATUTORY CHECKLIST (6 CLAUSES)',
    clause_net_wt: 'Net Quantity Statement',
    clause_mrp: 'MRP (Incl. of All Taxes)',
    clause_mfg_date: 'Month/Year of Packing',
    clause_mfr_address: 'Manufacturer Name & Address',
    clause_care_cell: 'Consumer Care Cell Contact',
    clause_usp: 'Unit Sale Price (USP) Decl.',

    // Bottom Action Bar
    enforcement_directives: 'Immediate Field Enforcement Directives',
    enforcement_subtitle: 'Statutory powers exercised under Section 15 & Section 36 of Legal Metrology Act, 2011',
    issue_form_v: 'Issue Form-V Inspection Memo',
    flag_compounding: 'Flag for Seizure / Compounding',
    export_hash: 'Export Hash Dossier (SHA-256)',
    proceed_to_certificate: 'Proceed to Certificate',

    // Footer
    footer_portal_name: 'PRAMAAN — Legal Metrology Compliance System',
    footer_dept: 'Department of Consumer Affairs, Ministry of Consumer Affairs, Food & Public Distribution, Krishi Bhawan, New Delhi - 110001',
    footer_nic_cert: 'NATIONAL INFORMATICS CENTRE CERTIFIED ENGINE',
    footer_iso: 'ISO 9001:2015 | G.S.R. 2026 AUDIT COMPLIANT',
    footer_copyright: '© 2026 Government of India, Department of Consumer Affairs. All rights reserved under statutory provisions of the Legal Metrology Act, 2011.',
    footer_terms: 'Website Policies',
    footer_manual: 'Help & FAQ',
    footer_gazette: 'Disclaimer',
    footer_privacy: 'Privacy Statement',
    footer_accessibility: 'Accessibility Statement',
    footer_last_updated: 'Last Reviewed and Updated',
    node_name: 'Node: NIC-DEL-CR01',
    satyamev_jayate: 'सत्यमेव जयते',
  },
  hi: {
    // Top Bar
    gov_india: 'भारत सरकार',
    gov_india_hindi: 'Government of India',
    ministry_title: 'उपभोक्ता मामले, खाद्य और सार्वजनिक वितरण मंत्रालय',
    dept_title: 'उपभोक्ता मामले विभाग',
    legal_metrology_div: 'विधिक मापविज्ञान प्रवर्तन प्रभाग • विधिक मापविज्ञान अधिनियम, 2011',
    portal_title: 'प्रमाण',
    portal_hindi_title: 'PRAMAAN',
    rules_subtitle: 'विधिक मापविज्ञान (पैकेज्ड कमोडिटीज) नियमावली, 2011',
    gazetted_enforcement: 'राजपत्रित क्षेत्रीय प्रवर्तन पोर्टल',
    network_online: 'नेटवर्क: ऑनलाइन',
    network_offline: 'नेटवर्क: ऑफ़लाइन',
    pending_sync: 'सिंक लंबित',
    inspector: 'निरीक्षक',
    active_on_duty: 'सक्रिय ड्यूटी पर',
    profile_badge: 'प्रोफ़ाइल',
    view_profile: 'अधिकारी परिचय डॉकेट',

    // Navigation Tabs
    tab_scan: 'प्रत्यक्ष निरीक्षण एवं स्कैन',
    tab_scan_sub: 'रियल-टाइम ऑप्टिकल ऑडिट',
    tab_certificate: 'विधिक प्रमाणपत्र एवं मेमो',
    tab_certificate_sub: 'फॉर्म-V / विधिक आदेश',
    tab_ledger: 'क्षेत्रीय निरीक्षण रजिस्टर',
    tab_ledger_sub: 'वैधानिक लेजर अभिलेख',
    tab_rules: 'विधिक नियम संग्रह (पीसीआर 2011)',
    tab_rules_sub: 'राजपत्र एवं नियम संदर्भ',

    // Marquee
    marquee_badge: 'राजपत्र अधिसूचना',
    marquee_badge_hi: 'GAZETTE DIRECTIVE',
    marquee_text:
      '[जी.एस.आर. 2026/वि.मा.] विधिक मापविज्ञान (पैकेज्ड कमोडिटीज) नियम, 2011 कड़ाई से लागू हैं। प्रत्येक पूर्व-पैक वस्तु पर नियम 6 के तहत निर्माता/पैकर/आयातकर्ता विवरण, अधिकतम खुदरा मूल्य (एमआरपी सभी करों सहित), मानक इकाइयों में शुद्ध मात्रा, विनिर्माण माह/वर्ष और उपभोक्ता हेल्पलाइन अनिवार्य है। विधिक मापविज्ञान अधिनियम, 2011 की धारा 15 एवं 36 के तहत डिजिटल फील्ड स्कैन और एसएचए-256 हैश रिकॉर्ड कानूनी रूप से बाध्यकारी साक्ष्य हैं। राष्ट्रीय उपभोक्ता हेल्पलाइन: 1915',

    // Ribbon
    ribbon_cadre: 'वैधानिक संवर्ग',
    ribbon_protocol: 'सुरक्षा प्रोटोकॉल',
    ribbon_act: 'अधिनियम',
    ribbon_act_val: 'विधिक मापविज्ञान अधिनियम, 2011 (2010 का सं. 1)',
    ribbon_hash: 'सुरक्षा हैश',
    ribbon_docket_active: 'आधिकारिक डॉकेट सक्रिय',
    ribbon_offline_mode: 'ऑफ़लाइन बफर मोड',

    // Live Scan View
    field_audit_title: 'क्षेत्रीय निरीक्षण अभिलेख',
    case_docket: 'रिपोर्ट संख्या',
    commodity: 'वस्तु / उत्पाद',
    inspection_location: 'निरीक्षण स्थल',
    capture_new_label: '+ नया लेबल स्कैन / कैप्चर करें',
    live_dossier_title: 'प्रत्यक्ष ऑप्टिकल मापविज्ञान ऑडिट एवं निरीक्षण विवरणिका',
    deficient_breach: 'उल्लंघन दर्ज (1 दोष)',
    fully_compliant: 'पूर्णतः अनुपालक',
    under_review: 'समीक्षाधीन',
    rule_summary_desc: 'विधिक मापविज्ञान (पैकेज्ड कमोडिटीज) नियमावली, 2011 एवं का.आ. 628(अ) के अंतर्गत स्वचालित वैधानिक अनुपालन मूल्यांकन।',
    total_clauses: 'कुल नियम खंड',
    valid_clauses: 'वैध',
    review_clauses: 'समीक्षा',
    defect_clauses: 'दोष',
    actionable_sec_36: 'धारा 36 अंतर्गत कार्रवाई योग्य',
    seizure_noticeable: 'जब्ती नोटिस जारी करने योग्य',
    all_rules_passed: 'वैधानिक रूप से स्वीकृत',

    // Viewport
    optical_viewport_title: 'ऑप्टिकल साक्ष्य व्यूपोर्ट',
    annotations_toggle: 'चिह्न/टैग',
    zoom_scale: 'माप ज़ूम',
    upload_own_image: 'पैकेज की फोटो अपलोड करें',
    scan_now_button: 'ऑप्टिकल मापविज्ञान स्कैन प्रारंभ करें',
    scanning_in_progress: 'पैकेज पर अंकित घोषणाओं का ऑप्टिकल विश्लेषण जारी है...',

    // Inspector Dossier Side Card
    inspection_findings: 'वैधानिक निरीक्षण निष्कर्ष एवं दोष विश्लेषण',
    rule_violated: 'उल्लंघन नियम',
    mandatory_requirement: 'अनिवार्य वैधानिक आवश्यकता',
    observed_detected: 'निरीक्षण में प्राप्त मान',
    font_geometry: 'फ़ॉन्ट आकार एवं स्थिति',
    prescribed_penalty: 'वैधानिक कार्रवाई / शास्ति',
    official_cadre_stamp: 'अधिकारी संवर्ग मुहर',

    // Checklist
    complete_checklist: 'सम्पूर्ण वैधानिक चेकलिस्ट (6 नियम खंड)',
    clause_net_wt: 'शुद्ध मात्रा घोषणा',
    clause_mrp: 'अधिकतम खुदरा मूल्य (सभी करों सहित)',
    clause_mfg_date: 'पैकिंग / विनिर्माण माह एवं वर्ष',
    clause_mfr_address: 'निर्माता / पैकर का नाम एवं पूर्ण पता',
    clause_care_cell: 'उपभोक्ता सेवा संपर्क सूत्र',
    clause_usp: 'इकाई विक्रय मूल्य (यूएसपी) घोषणा',

    // Bottom Action Bar
    enforcement_directives: 'तात्कालिक क्षेत्रीय प्रवर्तन निर्देश',
    enforcement_subtitle: 'विधिक मापविज्ञान अधिनियम, 2011 की धारा 15 एवं धारा 36 के अधीन प्रदत्त शक्तियों का प्रयोग',
    issue_form_v: 'फॉर्म-V निरीक्षण मेमो जारी करें',
    flag_compounding: 'जब्ती / शमन नोटिस हेतु चिह्नित करें',
    export_hash: 'एसएचए-256 हैश डॉकेट निर्यात करें',
    proceed_to_certificate: 'विधिक प्रमाणपत्र पर आगे बढ़ें',

    // Footer
    footer_portal_name: 'प्रमाण (PRAMAAN) — विधिक मापविज्ञान अनुपालन प्रणाली',
    footer_dept: 'उपभोक्ता मामले विभाग, उपभोक्ता मामले, खाद्य एवं सार्वजनिक वितरण मंत्रालय, कृषि भवन, नई दिल्ली - 110001',
    footer_nic_cert: 'राष्ट्रीय सूचना विज्ञान केंद्र (एनआईसी) प्रमाणित इंजन',
    footer_iso: 'आईएसओ 9001:2015 | जी.एस.आर. 2026 ऑडिट अनुपालक',
    footer_copyright: '© 2026 भारत सरकार, उपभोक्ता मामले विभाग। सर्वाधिकार सुरक्षित (विधिक मापविज्ञान अधिनियम, 2011 के वैधानिक प्रावधानों के अंतर्गत)।',
    footer_terms: 'वेबसाइट नीतियां',
    footer_manual: 'सहायता एवं अक्सर पूछे जाने वाले प्रश्न',
    footer_gazette: 'अस्वीकरण',
    footer_privacy: 'गोपनीयता नीति',
    footer_accessibility: 'सुलभता विवरण',
    footer_last_updated: 'अंतिम समीक्षा एवं अद्यतन',
    node_name: 'सर्वर नोड: एनआईसी-दिल्ली-सीआर01',
    satyamev_jayate: 'सत्यमेव जयते',
  },
};

interface LanguageContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  t: (key: keyof typeof translations['en']) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  lang: 'en',
  setLang: () => {},
  t: (key) => translations.en[key] || key,
});

export const LanguageProvider: React.FC<{ children: React.ReactNode; lang: Language; setLang: (l: Language) => void }> = ({
  children,
  lang,
  setLang,
}) => {
  const t = (key: keyof typeof translations['en']): string => {
    const currentDict = translations[lang] || translations.en;
    return (currentDict as Record<string, string>)[key] || translations.en[key] || key;
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
