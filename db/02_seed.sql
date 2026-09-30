-- Mock seed data. ALL names, phone numbers and addresses are fictional (demo only).

INSERT INTO cities (code, name_en, name_ar, country_code) VALUES
 ('jeddah', 'Jeddah', 'جدة',     'SA'),
 ('riyadh', 'Riyadh', 'الرياض',  'SA'),
 ('cairo',  'Cairo',  'القاهرة', 'EG'),
 ('dubai',  'Dubai',  'دبي',     'AE');

INSERT INTO specialties (code, name_en, name_ar) VALUES
 ('cardiology',        'Cardiology',        'أمراض القلب'),
 ('neurology',         'Neurology',         'المخ والأعصاب'),
 ('internal_medicine', 'Internal Medicine', 'الباطنة'),
 ('general_practice',  'General Practice',  'طب عام'),
 ('pulmonology',       'Pulmonology',       'أمراض الصدر'),
 ('gastroenterology',  'Gastroenterology',  'الجهاز الهضمي'),
 ('orthopedics',       'Orthopedics',       'العظام'),
 ('dermatology',       'Dermatology',       'الجلدية');

INSERT INTO languages (code, name_en, name_ar) VALUES
 ('ar', 'Arabic',  'العربية'),
 ('en', 'English', 'الإنجليزية'),
 ('fr', 'French',  'الفرنسية'),
 ('ur', 'Urdu',    'الأردية');

INSERT INTO hospitals (name_en, name_ar, city_id, address_en, address_ar, phone, has_emergency) VALUES
 ('Sahil Care Hospital',        'مستشفى ساحل كير',          (SELECT id FROM cities WHERE code='jeddah'), '12 Demo St, Al Rawdah, Jeddah',    '12 شارع تجريبي، الروضة، جدة',        '+966-12-000-0001', TRUE),
 ('Qamar Heart Institute',      'معهد قمر للقلب',            (SELECT id FROM cities WHERE code='jeddah'), '40 Demo Rd, Al Salamah, Jeddah',   '40 طريق تجريبي، السلامة، جدة',       '+966-12-000-0002', FALSE),
 ('Najd Medical City',          'مدينة نجد الطبية',          (SELECT id FROM cities WHERE code='riyadh'), '7 Demo Ave, Al Olaya, Riyadh',     '7 جادة تجريبية، العليا، الرياض',     '+966-11-000-0003', TRUE),
 ('Wadi Clinics',               'عيادات وادي',               (SELECT id FROM cities WHERE code='riyadh'), '88 Demo St, Al Malqa, Riyadh',     '88 شارع تجريبي، الملقا، الرياض',     '+966-11-000-0004', FALSE),
 ('Nile Valley Hospital',       'مستشفى وادي النيل',         (SELECT id FROM cities WHERE code='cairo'),  '3 Demo St, Zamalek, Cairo',        '3 شارع تجريبي، الزمالك، القاهرة',    '+20-2-0000-0005',  TRUE),
 ('Mokattam Specialist Center', 'مركز المقطم التخصصي',       (SELECT id FROM cities WHERE code='cairo'),  '21 Demo Rd, Mokattam, Cairo',      '21 طريق تجريبي، المقطم، القاهرة',    '+20-2-0000-0006',  FALSE),
 ('Creek Health Hospital',      'مستشفى كريك الصحي',         (SELECT id FROM cities WHERE code='dubai'),  '5 Demo Blvd, Bur Dubai, Dubai',    '5 بوليفارد تجريبي، بر دبي، دبي',     '+971-4-000-0007',  TRUE);

-- helper: doctors reference hospital/specialty by name/code to keep the seed readable
INSERT INTO doctors (name_en, name_ar, specialty_id, hospital_id, years_experience, accepts_second_opinion, offers_teleconsult)
SELECT d.name_en, d.name_ar, s.id, h.id, d.years, d.second_op, d.tele
FROM (VALUES
 -- Jeddah
 ('Dr. Faisal Al-Harbi',   'د. فيصل الحربي',   'cardiology',        'Qamar Heart Institute',      18, TRUE,  TRUE),
 ('Dr. Reem Al-Ghamdi',    'د. ريم الغامدي',   'cardiology',        'Sahil Care Hospital',        11, TRUE,  FALSE),
 ('Dr. Omar Bakr',         'د. عمر بكر',       'neurology',         'Sahil Care Hospital',        14, FALSE, TRUE),
 ('Dr. Huda Al-Zahrani',   'د. هدى الزهراني',  'internal_medicine', 'Sahil Care Hospital',         9, TRUE,  TRUE),
 ('Dr. Imran Qureshi',     'د. عمران قريشي',   'general_practice',  'Sahil Care Hospital',         6, FALSE, TRUE),
 ('Dr. Salma Idris',       'د. سلمى إدريس',    'pulmonology',       'Sahil Care Hospital',        12, TRUE,  FALSE),
 -- Riyadh
 ('Dr. Khalid Al-Otaibi',  'د. خالد العتيبي',  'cardiology',        'Najd Medical City',          22, TRUE,  TRUE),
 ('Dr. Nora Al-Qahtani',   'د. نورة القحطاني', 'neurology',         'Najd Medical City',          16, TRUE,  FALSE),
 ('Dr. Tariq Hassan',      'د. طارق حسن',      'gastroenterology',  'Wadi Clinics',               10, FALSE, TRUE),
 ('Dr. Lina Shaker',       'د. لينا شاكر',     'general_practice',  'Wadi Clinics',                7, FALSE, TRUE),
 ('Dr. Yousef Al-Dosari',  'د. يوسف الدوسري',  'orthopedics',       'Najd Medical City',          13, TRUE,  FALSE),
 -- Cairo
 ('Dr. Ahmed Mansour',     'د. أحمد منصور',    'cardiology',        'Nile Valley Hospital',       25, TRUE,  TRUE),
 ('Dr. Mona El-Sayed',     'د. منى السيد',     'cardiology',        'Mokattam Specialist Center', 8,  FALSE, TRUE),
 ('Dr. Karim Fawzy',       'د. كريم فوزي',     'neurology',         'Mokattam Specialist Center', 15, TRUE,  TRUE),
 ('Dr. Dina Ragab',        'د. دينا رجب',      'dermatology',       'Mokattam Specialist Center', 9,  FALSE, TRUE),
 ('Dr. Hany Soliman',      'د. هاني سليمان',   'internal_medicine', 'Nile Valley Hospital',       19, TRUE,  FALSE),
 -- Dubai
 ('Dr. Sara Haddad',       'د. سارة حداد',     'cardiology',        'Creek Health Hospital',      17, TRUE,  TRUE),
 ('Dr. Rahul Menon',       'د. راهول مينون',   'pulmonology',       'Creek Health Hospital',      12, TRUE,  TRUE),
 ('Dr. Claire Martin',     'د. كلير مارتن',    'general_practice',  'Creek Health Hospital',       5, FALSE, TRUE)
) AS d(name_en, name_ar, spec, hosp, years, second_op, tele)
JOIN specialties s ON s.code = d.spec
JOIN hospitals   h ON h.name_en = d.hosp;

INSERT INTO doctor_languages (doctor_id, language_code)
SELECT doc.id, l.lang
FROM (VALUES
 ('Dr. Faisal Al-Harbi', 'ar'), ('Dr. Faisal Al-Harbi', 'en'),
 ('Dr. Reem Al-Ghamdi', 'ar'),  ('Dr. Reem Al-Ghamdi', 'en'),
 ('Dr. Omar Bakr', 'ar'),
 ('Dr. Huda Al-Zahrani', 'ar'), ('Dr. Huda Al-Zahrani', 'en'),
 ('Dr. Imran Qureshi', 'en'),   ('Dr. Imran Qureshi', 'ur'),
 ('Dr. Salma Idris', 'ar'),     ('Dr. Salma Idris', 'en'),
 ('Dr. Khalid Al-Otaibi', 'ar'),('Dr. Khalid Al-Otaibi', 'en'),
 ('Dr. Nora Al-Qahtani', 'ar'), ('Dr. Nora Al-Qahtani', 'en'),
 ('Dr. Tariq Hassan', 'ar'),
 ('Dr. Lina Shaker', 'ar'),     ('Dr. Lina Shaker', 'en'),
 ('Dr. Yousef Al-Dosari', 'ar'),
 ('Dr. Ahmed Mansour', 'ar'),   ('Dr. Ahmed Mansour', 'en'), ('Dr. Ahmed Mansour', 'fr'),
 ('Dr. Mona El-Sayed', 'ar'),
 ('Dr. Karim Fawzy', 'ar'),     ('Dr. Karim Fawzy', 'en'),
 ('Dr. Dina Ragab', 'ar'),      ('Dr. Dina Ragab', 'en'),
 ('Dr. Hany Soliman', 'ar'),
 ('Dr. Sara Haddad', 'ar'),     ('Dr. Sara Haddad', 'en'), ('Dr. Sara Haddad', 'fr'),
 ('Dr. Rahul Menon', 'en'),
 ('Dr. Claire Martin', 'en'),   ('Dr. Claire Martin', 'fr')
) AS l(doc_name, lang)
JOIN doctors doc ON doc.name_en = l.doc_name;

-- Future slots relative to "now" so the demo always shows upcoming availability:
-- each doctor gets slots on days 1..10 at 06:00 and 11:00 UTC (09:00 / 14:00 Riyadh); ~30% randomly booked.
INSERT INTO availability_slots (doctor_id, starts_at, is_booked)
SELECT d.id,
       date_trunc('day', now()) + (day || ' days')::interval + (hr || ' hours')::interval,
       random() < 0.3
FROM doctors d
CROSS JOIN generate_series(1, 10) AS day
CROSS JOIN (VALUES (6), (11)) AS h(hr);
