# DoriLab Physics Source Register v0.1

확인일: 2026-09-13

기존 후보 12건 + 대체 출처 1건. 원문 텍스트 열람과 로컬 원본 확보를 구분한다. 이번 패키지에는 원본 PDF/PPTX가 동봉돼 있지 않다. 로컬 다운로드 실패 때문에 원문 SHA-256은 `null`이며, 사용자의 다운로드 성공 시 별도 acquisition manifest에 실제 해시를 계산한다.

## 실제 사용 출처

**TH-01**과 **VB-X1**의 PDF 본문 텍스트에서 16개 근거를 확인해 32개 가상 검토 사례를 작성했다. PDF 페이지 이미지는 도구의 fetch 오류로 확인하지 못했다. 따라서 표/그림의 수치를 옮긴 레코드는 이번에 넣지 않았다.

## 서지·출처 목록

### TH-01 — Apollo Telescope Mount Thermal Systems Unit Thermal Vacuum Test

- 저자: H. F. Trucks, Uwe Hueter, J. H. Wise, F. D. Bachtel
- 문서 유형: NASA Technical Note
- 서지 날짜: 1971-03-01 / PDF 날짜: 1972-03
- 보고서/DOI: NASA-TN-D-6646, M-372
- 서지 원문: https://ntrs.nasa.gov/citations/19720011230
- 원문 주소: https://ntrs.nasa.gov/api/citations/19720011230/downloads/19720011230.pdf
- 확인 범위: PDF_TEXT_REVIEWED
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: SEED32
- 프로그램 묶음: ATM_TSU
- 비고: NTRS catalog date is 1971-03-01; PDF title/report page text says March 1972. Both are retained as SOURCE_ISSUE SI-01.
- 비고: Seed cases use prose, not numerical table extraction. Raw PDF download and page rendering failed in the build environment.

### TH-02 — Analyses of Flight Model Spacecraft Performance During Thermal-Vacuum Tests

- 저자: A. R. Timmins, R. E. Heuser, J. C. Strain
- 문서 유형: NASA Technical Note
- 서지 날짜: 1973-11-01 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: NASA-TN-D-7408, G-7368
- 서지 원문: https://ntrs.nasa.gov/citations/19730025118
- 원문 주소: https://ntrs.nasa.gov/api/citations/19730025118/downloads/19730025118.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: MULTI_PROGRAM_39_FLIGHT_SPACECRAFT
- 비고: Catalog and abstract reviewed; full PDF fetch returned HTTP 403. No seed labels are derived from this source.

### TH-03 — A Physics-Based Temperature Stabilization Criterion for Thermal Testing

- 저자: Steven L. Rickman, Eugene K. Ungar
- 문서 유형: Conference Paper
- 서지 날짜: 2009-10-13 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: LF99-8634
- 서지 원문: https://ntrs.nasa.gov/citations/20090037689
- 원문 주소: https://ntrs.nasa.gov/api/citations/20090037689/downloads/20090037689.pdf
- 확인 범위: PDF_TEXT_REVIEWED
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: THERMAL_STABILIZATION_METHOD
- 비고: PDF text retrieved; no seed cases extracted from this source in v0.1.

### TH-04 — James Webb Space Telescope Integrated Science Instrument Module Thermal Vacuum Thermal Balance Test Campaign at NASA's Goddard Space Flight Center

- 저자: Stuart Glazer, Brian Comber
- 문서 유형: Presentation
- 서지 날짜: 2016-11-14 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: GSFC-E-DAA-TN36440
- 서지 원문: https://ntrs.nasa.gov/citations/20160013540
- 원문 주소: https://ntrs.nasa.gov/api/citations/20160013540/downloads/20160013540.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: JWST_ISIM
- 비고: NTRS classifies this record as Presentation, not journal paper. Public Use Permitted is recorded without changing it to US Government work. Full PDF fetch returned HTTP 403.

### VB-01 — Force Limited Vibration Testing Monograph

- 저자: Terry D. Scharton
- 문서 유형: Book / NASA Reference Publication
- 서지 날짜: 1997-05-01 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: NASA-RP-1403
- 서지 원문: https://ntrs.nasa.gov/citations/19970023193
- 원문 주소: https://ntrs.nasa.gov/api/citations/19970023193/downloads/19970023193.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: FLVT_MONOGRAPH_MULTI_PROGRAM
- 비고: Full PDF returned HTTP 403. No page-level extraction or seed labels attributed to this monograph. VB-X1 supplies the first vibration seed cases instead.

### VB-02 — Benefits of Force Limiting Vibration Testing

- 저자: Mark E. McNelis, Terry D. Scharton
- 문서 유형: Reprint (Version printed in journal)
- 서지 날짜: 1999-08-01 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: NASA/TM-1999-209382, E-11809
- 서지 원문: https://ntrs.nasa.gov/citations/19990095797
- 원문 주소: https://ntrs.nasa.gov/api/citations/19990095797/downloads/19990095797.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: COMBUSTION_MODULE_2_CAMERA
- 비고: Catalog and abstract reviewed; full PDF fetch returned HTTP 403.

### VB-03 — Application of the Semi-Empirical Force-Limiting Approach for the CoNNeCT SCAN Testbed

- 저자: Lucas D. Staab, Mark E. McNelis, James C. Akers, Vicente J. Suarez, Trevor M. Jones
- 문서 유형: Technical Memorandum
- 서지 날짜: 2012-09-01 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: NASA/TM-2012-217627, E-18217
- 서지 원문: https://ntrs.nasa.gov/citations/20120014221
- 원문 주소: https://ntrs.nasa.gov/api/citations/20120014221/downloads/20120014221.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: CONNECT_SCAN_TESTBED
- 비고: Catalog and abstract reviewed; full PDF fetch returned HTTP 403.

### VB-04 — Benefits of Spacecraft Level Vibration Testing

- 저자: Scott Gordon, Dennis L. Kern
- 문서 유형: Conference Paper
- 서지 날짜: 2015-10-27 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: GSFC-E-DAA-TN26994
- 서지 원문: https://ntrs.nasa.gov/citations/20150020490
- 원문 주소: https://ntrs.nasa.gov/api/citations/20150020490/downloads/20150020490.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Public Use Permitted.
- 계획 역할: TRAIN / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: NASA_GSFC_JPL_MULTI_PROGRAM_VIBRATION
- 비고: Public Use Permitted, not an explicit Government-work statement. Mission overlap with reserved evaluation sources requires a later full-text audit. PDF fetch returned HTTP 403.

### TH-D1 — Transient thermal parameters correlation of spacecraft thermal models against test results

- 저자: Iñaki Garmendia, Eva Anglada
- 문서 유형: Journal Article
- 서지 날짜: 2022-10 / PDF 날짜: 2022-07-14 (available online)
- 보고서/DOI: 10.1016/j.actaastro.2022.07.014
- 서지 원문: https://dsp.tecnalia.com/items/69c999d9-edd2-4b36-95cb-2ffedfb0218b
- 원문 주소: https://dsp.tecnalia.com/bitstreams/44f57fa6-857e-40b0-b500-e79503277642/download
- 확인 범위: PDF_TEXT_REVIEWED
- 원문 권리 표기: © 2022 The Authors. Published by Elsevier Ltd on behalf of IAA. This is an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/).
- 계획 역할: DEV_RESERVED / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: TRIBOLAB_ISS_TMM
- 라이선스: https://creativecommons.org/licenses/by/4.0/
- 비고: PDF text and CC BY 4.0 notice checked. No cases or RAG chunks exported for this source.

### VB-D1 — Dynamic Finite Element Model Correlation

- 저자: James P. Winkel
- 문서 유형: Presentation
- 서지 날짜: 서지 미표시 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: 없음
- 서지 원문: https://ntrs.nasa.gov/citations/20220016063
- 원문 주소: https://ntrs.nasa.gov/api/citations/20220016063/downloads/Joint_Talk_Presentation_2022_Final.pptx
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: DEV_RESERVED / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: JOINT_MECHANICS_MULTI_PROGRAM_NEEDS_AUDIT
- 비고: The listed original download is PPTX, not PDF. Seminar date 2022-11-08; acquisition date 2022-10-25. Program overlap with E-STA must be checked before calling the split independent.

### TH-S1 — Thermal Testing and Model Correlation of the Magnetospheric Multiscale (MMS) Observatories

- 저자: Jong S. Kim, Nicholas M. Teti
- 문서 유형: Conference Paper
- 서지 날짜: 2015-07-12 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: ICES-2015-331, GSFC-E-DAA-TN24401
- 서지 원문: https://ntrs.nasa.gov/citations/20150018320
- 원문 주소: https://ntrs.nasa.gov/api/citations/20150018320/downloads/20150018320.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Public Use Permitted.
- 계획 역할: EVAL_RESERVED / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: MMS
- 비고: Catalog and abstract reviewed only; full PDF fetch returned HTTP 403. Reserved means no cases generated here, not that this public source is unknown to the base model.

### VB-S1 — European Service Module - Structural Test Article (E-STA) Building Block Test Approach and Model Correlation Observations

- 저자: James P. Winkel, Samantha A. Bittinger, Vicente J. Suarez, James C. Akers
- 문서 유형: Conference Paper
- 서지 날짜: 2019-01-28 / PDF 날짜: 별도 확인 없음
- 보고서/DOI: GRC-E-DAA-TN61845
- 서지 원문: https://ntrs.nasa.gov/citations/20190001819
- 원문 주소: https://ntrs.nasa.gov/api/citations/20190001819/downloads/20190001819.pdf
- 확인 범위: CATALOG_ONLY
- 원문 권리 표기: Work of the US Gov. Public Use Permitted.
- 계획 역할: EVAL_RESERVED / 이번 사용: RESERVED_CANDIDATE
- 프로그램 묶음: ORION_ESM_ESTA
- 비고: Catalog and abstract reviewed; full PDF fetch returned HTTP 403. Cross-document mission overlap remains to be audited.

### VB-X1 — Force limited random vibration testing: the computation of the semi-empirical constant C² for a real test article and unknown supporting structure

- 저자: J. J. Wijker, M. H. M. Ellenbroek, A. de Boer
- 문서 유형: Journal Article
- 서지 날짜: 2015-04-14 / PDF 날짜: 2015-04-14
- 보고서/DOI: 10.1007/s12567-015-0086-0
- 서지 원문: https://link.springer.com/article/10.1007/s12567-015-0086-0
- 원문 주소: https://link.springer.com/content/pdf/10.1007/s12567-015-0086-0.pdf
- 확인 범위: PDF_TEXT_REVIEWED
- 원문 권리 표기: This article is distributed under the terms of the Creative Commons Attribution 4.0 International License.
- 계획 역할: TRAIN / 이번 사용: SEED32
- 프로그램 묶음: JWST_MIRI_IFLV, ISS_LINEAR_DRIVE_UNIT
- 라이선스: https://creativecommons.org/licenses/by/4.0/
- 비고: Explicit alternative for inaccessible VB-01; not a copy or substitute citation for the monograph.
- 비고: This paper analyzes two testcases from prior literature; it does not supply a new full raw flight-test dataset.
- 비고: Inputs and labels below are new counterfactual scenarios; paper principles are paraphrased with attribution.

## 검수 중 확인한 수정사항

1. Apollo: 서지 1971-03-01과 PDF 표제지 텍스트 March 1972가 다르다. 어느 하나를 지우지 않고 SourceIssue SI-01로 관리한다.
2. VB-D1은 PDF 논문이 아니라 PPTX 발표자료다. 원본 이름은 `Joint_Talk_Presentation_2022_Final.pptx`이다.
3. TH-04, VB-04, TH-S1의 권리 표기는 `Public Use Permitted.`이며 `Work of the US Gov.`와 구분한다.
4. VB-01은 원문 접근 실패로 32개 사례의 근거가 아니다. VB-X1의 논문명·페이지·CC BY 출처를 별도로 표시한다.
5. Wijker 논문은 기존 두 시험 사례를 분석한 방법론 논문이다. 16개 진동 사례는 그 원리로 새로 구성한 가상 검토이며 논문 원시 실험값을 제공하는 데이터셋이 아니다.
6. 동일 임무가 여러 논문·발표에 재등장할 수 있다. 최종 평가 전 문서 ID뿐 아니라 실제 시험체·임무·유래 데이터 단위로 중복을 확인한다.
