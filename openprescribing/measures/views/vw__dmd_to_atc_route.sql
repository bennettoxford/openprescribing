SELECT DISTINCT
  ofr.descr AS dmd_ofr,
  SPLIT(ofr.descr, '.')[OFFSET(1)] AS dmd_r,
  CASE
    WHEN ofr.descr = 'implant.subcutaneous' THEN 'implant'
    WHEN ofr.descr = 'pressurizedinhalation.inhalation' THEN 'Inhal.aerosol'
    WHEN ofr.descr = 'powderinhalation.inhalation' THEN 'Inhal.powder'
    WHEN ofr.descr = 'solutionnebuliser.inhalation' THEN 'Inhal.solution'
    WHEN ofr.descr = 'dispersionnebuliser.inhalation' THEN 'Inhal.solution' -- amikacin liposomal
    WHEN ofr.descr = 'inhalationsolution.inhalation' THEN 'Inhal.solution' -- mist inhalers - e.g. tiotropium respimat
    WHEN ofr.descr = 'suspensionnebuliser.inhalation' THEN 'Inhal.solution' -- steroid nebs
    WHEN ofr.descr = 'medicatedchewing-gum.oromucosal' THEN 'Chewing gum' -- nicotine
    WHEN ofr.descr = 'solution.oromucosal' THEN 'SL' -- midazolam oromucosal
    WHEN ofr.descr = 'tabletsublingual.oromucosal' THEN 'SL'
    WHEN ofr.descr = 'lozenge.oromucosal' THEN 'SL' -- fentanyl lozenge
    WHEN ofr.descr = 'lyophilisate.oromucosal' THEN 'SL' -- buprenorphine
    WHEN ofr.descr = 'filmsublingual.oromucosal' THEN 'SL' -- buprenorphine
    WHEN ofr.descr = 'vapour.oromucosal' THEN 'Inhal' -- nicotine inhalator - to match ATC
    WHEN ofr.descr LIKE '%.oral' THEN 'O'
    WHEN ofr.descr LIKE '%.gastroenteral' THEN 'O'
    WHEN ofr.descr LIKE '%.intravenous' THEN 'P'
    WHEN ofr.descr LIKE '%.intramuscular%' THEN 'P'
    WHEN ofr.descr LIKE '%.subcutaneous' THEN 'P'
    WHEN ofr.descr LIKE '%.intracavernous' THEN 'P'
    WHEN ofr.descr LIKE '%.intracardiac' THEN 'P'   
    WHEN ofr.descr LIKE '%.intracoronary' THEN 'P'  
    WHEN ofr.descr LIKE '%.vaginal' THEN 'V'
    WHEN ofr.descr LIKE '%.rectal' THEN 'R'
    WHEN ofr.descr LIKE '%.submucosalrectal' THEN 'R'
    WHEN ofr.descr LIKE '%.nasal' THEN 'N'
    WHEN ofr.descr LIKE '%.buccal' THEN 'SL'
    WHEN ofr.descr LIKE '%.sublingual' THEN 'SL'
    WHEN ofr.descr LIKE '%.transdermal' THEN 'TD'
    WHEN ofr.descr LIKE '%.urethral' THEN 'urethral'   
    WHEN ofr.descr LIKE '%.intravesical' THEN 'intravesical'


  END AS who_route
  FROM `ebmdatalab.dmd.vmp` vmp
LEFT JOIN dmd.ont ont ON vmp.id = ont.vmp
LEFT JOIN dmd.ontformroute ofr ON ont.form = ofr.cd
LEFT JOIN dmd.droute droute ON vmp.id = droute.vmp
LEFT JOIN dmd.route route ON droute.route = route.cd
WHERE route.descr IS NOT NULL 
AND ofr.descr IS NOT NULL
AND ofr.descr NOT LIKE '%.auricular' -- eye drops don't seem to have DDDs
AND ofr.descr NOT LIKE '%.bodycavity' -- ??
AND ofr.descr NOT LIKE '%.cutaneous' -- no DDDs
AND ofr.descr NOT LIKE '%.dental' -- mostly sodium fluoride toothpaste, chlorhexidine mouthwash - no obvious route match
AND ofr.descr NOT LIKE '%.endocervical' -- no obvious route match
AND ofr.descr NOT LIKE '%.endosinusial'-- no obvious route match
AND ofr.descr NOT LIKE '%.endotracheopulmonary' -- possibly match on inhalation, but not much here with DDDs
AND ofr.descr NOT LIKE '%.epidural' -- no obvious route match/ no relevent DDDs e.g. bupivacaine
AND ofr.descr NOT LIKE '%.epilesional'-- no obvious route match
AND ofr.descr NOT LIKE '%.extraamniotic'-- no obvious route match
AND ofr.descr NOT LIKE '%.extracorporeal'-- no obvious route match
AND ofr.descr NOT LIKE '%.gingival'-- no obvious route match
AND ofr.descr NOT LIKE '%.haemodialysis'-- no obvious route match
AND ofr.descr NOT LIKE '%.haemofiltration'-- no obvious route match
AND ofr.descr NOT LIKE '%.implantation'-- no obvious route match. Not to be confused with subcutaneous implants
AND ofr.descr NOT LIKE '%.infiltration'-- no obvious route match
AND ofr.descr NOT LIKE '%.scalp'-- no obvious route match
AND ofr.descr NOT LIKE '%.ophthalmic'-- no obvious route match
AND ofr.descr NOT LIKE '%.opthalmic'-- typo for above
AND ofr.descr NOT LIKE '%.intestinal'-- levodopa gels for Parkinson's disease
AND ofr.descr NOT LIKE '%.intraarterial'-- contrast media. A few specific drugs but the probably also have a more common P route.
AND ofr.descr NOT LIKE '%.intraarticular'-- limited interest
AND ofr.descr NOT LIKE '%.intrabursal'-- limited interest
AND ofr.descr NOT LIKE '%.intracameral'-- niche
AND ofr.descr NOT LIKE '%.intracerebroventricular'-- niche
AND ofr.descr NOT LIKE '%.intracholangiopancreatic'-- contrast media
AND ofr.descr NOT LIKE '%.intradermal'-- limited interest - a few vaccines - probably no DDDs
AND ofr.descr NOT LIKE '%.intradiscal'-- niche
AND ofr.descr NOT LIKE '%.intraepidermal'-- skin prick tests
AND ofr.descr NOT LIKE '%.intraglandular'-- contrast / Botox
AND ofr.descr NOT LIKE '%.intralesional'-- contrast media. A few specific drugs but the probably also have a more common P route.
AND ofr.descr NOT LIKE '%.intraocular'-- no obvious route match
AND ofr.descr NOT LIKE '%.intraosseous'-- A few specific drugs but the probably also have a more common P route.
AND ofr.descr NOT LIKE '%.intraperitoneal'-- no obvious route match
AND ofr.descr NOT LIKE '%.intrapleural'-- niche
AND ofr.descr NOT LIKE '%.intraputaminal'-- putamen = part of brain. Very niche - 1 product - gene therapy
AND ofr.descr NOT LIKE '%.intrathecal'-- A few specific drugs but the probably also have a more common P route.
AND ofr.descr NOT LIKE '%.intratumoral'-- niche
AND ofr.descr NOT LIKE '%.intrauterine'-- no obvious route
AND ofr.descr NOT LIKE '%.intraventricular cardiac'-- niche
AND ofr.descr NOT LIKE '%.intravitreal'-- no obvious route. No DDDs for those of interest.
AND ofr.descr NOT LIKE '%.iontophoresis'-- no obvious route
AND ofr.descr NOT LIKE '%.linelock'-- no obvious route
AND ofr.descr NOT LIKE '%.ocular'-- no obvious route
AND ofr.descr NOT LIKE '%.periarticular'-- no obvious route
AND ofr.descr NOT LIKE '%.peribulbar ocular'-- no obvious route
AND ofr.descr NOT LIKE '%.perilesional'-- no obvious route
AND ofr.descr NOT LIKE '%.perineural'-- no obvious route, niche
AND ofr.descr NOT LIKE '%.peritumoral'-- no obvious route
AND ofr.descr NOT LIKE '%.regionalperfusion'-- no obvious route
AND ofr.descr NOT LIKE '%.subconjunctival'-- no obvious route
AND ofr.descr NOT LIKE '%.submucosal'-- no obvious route, small number of products with a more common P route
AND ofr.descr NOT LIKE '%.subretinal'-- no obvious route
AND ofr.descr != 'gasinhalation.inhalation' -- medical gases
AND ofr.descr != 'vapourinhalationliquid.inhalation' -- inhaled anaesthetics
AND ofr.descr != 'vapourinhalation.inhalation' -- only 1 product - Benzoin compound tincture
AND ofr.descr != 'impregnatedcigarette.inhalation' -- no DDDs
AND ofr.descr NOT IN ('gargle.oromucosal', 'gel.oromucosal', 'homeopathicpillule.oromucosal', 'liquid.oromucosal', 'liquidspray.oromucosal', 'mouthwash.oromucosal', 'paste.oromucosal', 'homeopathictablet.oromucosal', 'pastille.oromucosal', 'solutionspray.oromucosal', 'suspension.oromucosal', 'suspensionspray.oromucosal', 'tabletmuco-adhesive.oromucosal', 'vapour.oromucosal') -- no DDDs
ORDER BY who_route, dmd_r ASC