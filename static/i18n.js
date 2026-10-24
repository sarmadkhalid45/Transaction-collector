const TRANSLATIONS = {
  en: {
    brand: "LedgerBridge",
    brand_sub: "Private transaction collection",
    logout: "Sign out",
    auth_eyebrow: "Secure transaction workspace",
    tab_signin: "Sign in",
    tab_register: "Create account",
    password_label: "Password (12 characters minimum)",
    notice_label: "Data sharing notice:",
    consent_label:
      "I understand and consent to sharing my transaction records with the system administrator for reporting and monitoring.",
    auth_submit_login: "Sign in",
    auth_submit_register: "Create account",
    footnote:
      "Use only fictional data for testing. Consent can be withdrawn by deleting your account; already synchronized spreadsheet copies may remain under the administrator's retention policy.",
    role_label_admin: "Administrator console",
    role_label_user: "Your workspace",
    page_title_admin: "Collection overview",
    page_title_user: "Transactions",
    page_sub_admin:
      "Review all submitted records, sync health, and account access.",
    page_sub_user: "Record and review transactions in your private account.",
    admin_section_title: "Reporting filters",
    export_csv: "Export CSV",
    edit_tx_title: "Edit transaction",
    cancel_btn: "Cancel",
    save_btn: "Save corrected entry",
    admin_table_title: "All submitted transactions",
    user_access_title: "User access",
    suspend_title: "Suspend or restore registration access",
    form_title_add: "Add transaction",
    form_title_edit: "Edit transaction",
    cancel_edit: "Cancel edit",
    history_title: "Your transaction history",
    empty: "No transactions found.",
    empty_records: "No records found.",
    empty_users: "No registered users.",
    btn_edit: "Edit",
    btn_retry: "Retry sync",
    btn_delete: "Delete",
    delete_confirm:
      "Hide this transaction from your history? Already synchronized copies are not removed from the administrator spreadsheet.",
    delete_success: "Transaction removed from your history",
    delete_account_confirm:
      "Permanently delete your account and local records? Copies already sent to the administrator spreadsheet may remain.",
    delete_account_success: "Account and local records deleted",
    delete_account_btn: "Delete my account and records",
    apply_filters: "Apply",
    clear_filters: "Reset",
    suspend_confirm:
      "Suspend this account? The user will be signed out on their next request.",
    sync_status_prefix: "Sync status: ",
    sync_status_pending: "pending",
    sync_status_success: "success",
    sync_status_failed: "failed",
    toast_saved: "Transaction saved",
    toast_updated: "Transaction updated",
    toast_corrected: "Transaction corrected and saved",
    total_label: "Transactions",
    income_label: "Income",
    expenses_label: "Expenses",
    net_label: "Net flow",
    login_required: "Please sign in to continue.",
    option_income: "Income",
    option_expense: "Expense",
    option_transfer: "Transfer",
    option_other: "Other",
  },
  ar: {
    brand: "LedgerBridge",
    brand_sub: "مجموعة معاملات خاصة",
    logout: "تسجيل الخروج",
    auth_eyebrow: "مساحة معاملات آمنة",
    tab_signin: "تسجيل الدخول",
    tab_register: "إنشاء حساب",
    password_label: "كلمة المرور (12 حرفًا كحد أدنى)",
    notice_label: "إشعار مشاركة البيانات:",
    consent_label:
      "أنا أفهم وأوافق على مشاركة سجلات معاملاتي مع مسؤول النظام لأغراض التقارير والمراقبة.",
    auth_submit_login: "تسجيل الدخول",
    auth_submit_register: "إنشاء حساب",
    footnote:
      "استخدم بيانات وهمية فقط للاختبار. يمكن سحب الموافقة بحذف حسابك؛ قد تبقى نسخ جدول البيانات المتزامنة تحت سياسة الاحتفاظ للمسؤول.",
    role_label_admin: "وحدة المشرف",
    role_label_user: "مساحة العمل",
    page_title_admin: "نظرة عامة على المجموعة",
    page_title_user: "معاملاتك",
    page_sub_admin: "مراجعة جميع السجلات المقدمة وصحة المزامنة ووصول الحسابات.",
    page_sub_user: "تسجيل ومراجعة المعاملات في حسابك الخاص.",
    admin_section_title: "فلاتر التقارير",
    export_csv: "تصدير CSV",
    edit_tx_title: "تعديل المعاملة",
    cancel_btn: "إلغاء",
    save_btn: "حفظ التصحيح",
    admin_table_title: "جميع المعاملات المقدمة",
    user_access_title: "وصول المستخدمين",
    suspend_title: "تعليق أو استعادة الوصول للتسجيل",
    form_title_add: "إضافة معاملة",
    form_title_edit: "تعديل المعاملة",
    cancel_edit: "إلغاء التعديل",
    history_title: "سجل معاملاتك",
    empty: "لا توجد معاملات.",
    empty_records: "لا توجد سجلات.",
    empty_users: "لا يوجد مستخدمون مسجلون.",
    btn_edit: "تعديل",
    btn_retry: "إعادة مزامنة",
    btn_delete: "حذف",
    delete_confirm:
      "إخفاء هذه المعاملة من السجل؟ لا تتم إزالة النسخ المتزامنة من جدول المسؤول.",
    delete_success: "تمت إزالة المعاملة من السجل",
    delete_account_confirm:
      "حذف حسابك والسجلات المحلية بشكل دائم؟ قد تبقى النسخ المرسلة لجدول المسؤول.",
    delete_account_success: "تم حذف الحساب والسجلات المحلية",
    delete_account_btn: "حذف حسابي وسجلاتي",
    apply_filters: "تطبيق",
    clear_filters: "إعادة تعيين",
    suspend_confirm:
      "تعليق هذا الحساب؟ سيتم تسجيل خروج المستخدم في طلبه التالي.",
    sync_status_prefix: "حالة المزامنة: ",
    sync_status_pending: "قيد الانتظار",
    sync_status_success: "ناجح",
    sync_status_failed: "فشل",
    toast_saved: "تم حفظ المعاملة",
    toast_updated: "تم تحديث المعاملة",
    toast_corrected: "تم تصحيح المعاملة وحفظها",
    total_label: "المعاملات",
    income_label: "الدخل",
    expenses_label: "المصروفات",
    net_label: "صافي التدفق",
    login_required: "يرجى تسجيل الدخول للمتابعة.",
    option_income: "دخل",
    option_expense: "مصروف",
    option_transfer: "تحويل",
    option_other: "أخرى",
  },
  ur: {
    brand: "LedgerBridge",
    brand_sub: "نجی لینس کرنے کا مقام",
    logout: "لاگ آؤٹ",
    auth_eyebrow: "محفوظ لینس کرنے کا مقام",
    tab_signin: "سائن ان",
    tab_register: "اکاؤنٹ بنائیں",
    password_label: "پاس ورڈ (کم از کم 12 حروف)",
    notice_label: "ڈیٹا شیئرنگ نوٹس:",
    consent_label:
      "میں اپنی ٹرانزیکشن ریکارڈز کو رپورٹنگ اور نگرانی کے لیے منتظم کے ساتھ شیئر کرنے پر رضامند ہوں۔",
    auth_submit_login: "سائن ان",
    auth_submit_register: "اکاؤنٹ بنائیں",
    footnote:
      "ٹیسٹنگ کے لیے صرف خیالی ڈیٹا استعمال کریں۔ اکاؤنٹ حذف کرکے رضامندی واپس لی سکتے ہیں؛ پہلے سے ہم آہنگ کیا ہوا اسپریڈشیٹ نسخہ منتظم کی پالیسی کے تحت رہ سکتا ہے۔",
    role_label_admin: "ایڈمن کنسول",
    role_label_user: "آپ کا ورک سپیس",
    page_title_admin: "جمع کا جائزہ",
    page_title_user: "آپ کی ٹرانزیکشنز",
    page_sub_admin: "جمع کردہ تمام ریکارڈز، سنک کی صحت، اور اکاؤنٹ تک رسائی کا جائزہ لیں۔",
    page_sub_user: "اپنے نجی اکاؤنٹ میں ٹرانزیکشنز ریکارڈ اور جائزہ لیں۔",
    admin_section_title: "رپورٹنگ فلٹرز",
    export_csv: "CSV برآمد",
    edit_tx_title: "ٹرانزیکشن میں ترمیم",
    cancel_btn: "منسوخ",
    save_btn: "صحیح اندراج محفوظ کریں",
    admin_table_title: "جمع کردہ تمام ٹرانزیکشنز",
    user_access_title: "صارفون تک رسائی",
    suspend_title: "رجسٹریشن رسائی معطل یا بحال کریں",
    form_title_add: "ٹرانزیکشن شامل کریں",
    form_title_edit: "ٹرانزیکشن میں ترمیم کریں",
    cancel_edit: "ترمیم منسوخ کریں",
    history_title: "آپ کی ٹرانزیکشن کی تاریخ",
    empty: "کوئی ٹرانزیکشن نہیں ملا۔",
    empty_records: "کوئی ریکارڈ نہیں ملا۔",
    empty_users: "کوئی رجسٹرڈ صارف نہیں۔",
    btn_edit: "ترمیم",
    btn_retry: "دوبارہ سنک کریں",
    btn_delete: "حذف کریں",
    delete_confirm:
      "اس ٹرانزیکشن کو اپنے تاريخ سے چھپائیں؟ منتظم کے اسپریڈشیٹ میں ہم آہنگ کردہ نسخے خود بخود حذف نہیں ہوتے۔",
    delete_success: "ٹرانزیکشن تاريخ سے حذف ہو گئی",
    delete_account_confirm:
      "اپنا اکاؤنٹ اور مقامی ریکارڈز مستقل حذف کریں؟ منتظم کے اسپریڈشیٹ میں بھیجے گئے نسخہ باقی رہ سکتا ہے۔",
    delete_account_success: "اکاؤنٹ اور مقامی ریکارڈز حذف ہو گئے",
    delete_account_btn: "میرا اکاؤنٹ اور ریکارڈز حذف کریں",
    apply_filters: "لگا دیں",
    clear_filters: "ری سیٹ",
    suspend_confirm:
      "اس اکاؤنٹ کی رسائی معطل کریں؟ صارف اگلے درخواست پر لاگ آؤٹ ہو جائے گا۔",
    sync_status_prefix: "سنک کی حیثیت: ",
    sync_status_pending: "زیر التواء",
    sync_status_success: "کامیاب",
    sync_status_failed: "ناکام",
    toast_saved: "ٹرانزیکشن محفوظ ہو گئی",
    toast_updated: "ٹرانزیکشن اپ ڈیٹ ہو گئی",
    toast_corrected: "ٹرانزیکشن درست کر کے محفوظ ہو گئی",
    total_label: "ٹرانزیکشنز",
    income_label: "آمد",
    expenses_label: "خرچہ",
    net_label: "خالص رقوم",
    login_required: "جاری رکھنے کے لیے براہ کرم لاگ ان کریں۔",
    option_income: "آمد",
    option_expense: "خرچہ",
    option_transfer: "منتقل",
    option_other: "دیگر",
  },
};

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

function t(key) {
  return (window.__i18n && window.__i18n[key]) || key;
}

async function loadLocale(lang) {
  try {
    const r = await fetch(`/api/locales/${lang}`);
    if (!r.ok) throw new Error("Locale not found");
    window.__i18n = await r.json();
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" || lang === "ur" ? "rtl" : "ltr";
    const sel = $("lang-switch");
    if (sel) sel.value = lang;
    localStorage.setItem("lang", lang);
    applyTranslations();
  } catch (e) {
    console.error("Failed to load locale", e);
  }
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    const text = t(key);
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      if (!el.getAttribute("placeholder") && el.value === text) {
        el.placeholder = text;
      }
    } else {
      el.textContent = text;
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
  });
}

function initLocale() {
  window.__localeReady = (async () => {
    const saved = localStorage.getItem("lang") || "en";
    await loadLocale(saved);
    const sel = $("lang-switch");
    if (sel) {
      sel.addEventListener("change", async (e) => {
        await loadLocale(e.target.value);
        location.reload();
      });
    }
  })();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initLocale);
} else {
  initLocale();
}
