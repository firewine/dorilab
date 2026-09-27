# v12 — reason coverage training candidates



AI 작성·AI 논리검토. 실제 시험자료나 사람 승인 아님. NS10 평가자료는 학습에 포함하지 않음.

단일 관측으로 범위를 정리한 신규 사례를 사용하며 기존 210행의 위치 증강 사례는 그대로 replay한다.

새로운 36개 상태는 18개 관련 쌍이다. 기존 반복 60행도 고유 Physics 20개일 뿐이다.

source fact는 기존 제공 패킷의 발췌를 재사용한다. VB-X1 식(2)와 C² 선정 문단만 공개 출판사 HTML에서 다시 확인했다. PDF 전체/원시 시험값을 새로 검증하지 않았다.

대조군과 학습군은 행 수·action 노출·데이터 슬롯·epoch를 맞추지만 입력 길이·정답 토큰 수는 같지 않다. 단일 seed의 개발 실험이다.



## RC12-C1-A

노출·관측 자료는 유지하고 시험 당시 전기적 구성 기록만 바꾼다. 없는 항목은 노출량이나 파형이 아닌 bias/운용모드이므로 구성 추적성 분류를 사용한다. 범위키 존재와 실제 설정 기록의 완전성은 다르다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U201; configuration=RC12-C301; run=RC12-R401. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the bias and operating-mode settings traceable to the identified irradiation run? Review operating-configuration records only; exposure and event coverage are already available.

**제안:** Complete the as-tested operating-configuration record check for this run.

**가상 관측:** Record scope: unit=RC12-U201; configuration=RC12-C301; run=RC12-R401. The exposure file and event time series are complete and linked to this run. The electrical setup form has empty bias and operating-mode entries. The specimen label and run identifier are present; neither missing setting can be recovered from another record.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-939063","evidence_refs":["SF-271358","OBS-472443"],"reason":"CONFIGURATION_SCOPE_UNRESOLVED","requested_evidence":["AS_TESTED_OPERATING_CONFIGURATION"]}`



## RC12-C1-B

노출·관측 자료는 유지하고 시험 당시 전기적 구성 기록만 바꾼다. 없는 항목은 노출량이나 파형이 아닌 bias/운용모드이므로 구성 추적성 분류를 사용한다. 범위키 존재와 실제 설정 기록의 완전성은 다르다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U201; configuration=RC12-C301; run=RC12-R401. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the bias and operating-mode settings traceable to the identified irradiation run? Review operating-configuration records only; exposure and event coverage are already available.

**제안:** Complete the as-tested operating-configuration record check for this run.

**가상 관측:** Record scope: unit=RC12-U201; configuration=RC12-C301; run=RC12-R401. The exposure file and event time series are complete and linked to this run. The electrical setup form records the applied bias and operating mode, and its header matches the specimen and run identifiers.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-939063","evidence_refs":["SF-271358","OBS-472443"]}`



## RC12-C2-A

기록이 둘 다 존재해도 실제 사용한 설정을 대응할 수 없으면 구성 연결 자료를 요청한다. 양쪽 설정이 모두 잘못됐다는 판단이나 관측 범위 부족으로 바꾸지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U202; configuration=RC12-C302; run=RC12-R402. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Can the electrical setup revision actually used in this run be identified? The check is traceability of the run to the setup, not a radiation-effects verdict.

**제안:** Resolve the run-to-electrical-setup linkage before interpreting the result.

**가상 관측:** Record scope: unit=RC12-U202; configuration=RC12-C302; run=RC12-R402. Two signed electrical setup sheets list different bias and mode settings. The run log identifies the specimen, contains complete exposure and event records, and explicitly names which setup-sheet revision was used during the interval.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-583480","evidence_refs":["SF-381825","OBS-658379"]}`



## RC12-C2-B

기록이 둘 다 존재해도 실제 사용한 설정을 대응할 수 없으면 구성 연결 자료를 요청한다. 양쪽 설정이 모두 잘못됐다는 판단이나 관측 범위 부족으로 바꾸지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U202; configuration=RC12-C302; run=RC12-R402. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Can the electrical setup revision actually used in this run be identified? The check is traceability of the run to the setup, not a radiation-effects verdict.

**제안:** Resolve the run-to-electrical-setup linkage before interpreting the result.

**가상 관측:** Record scope: unit=RC12-U202; configuration=RC12-C302; run=RC12-R402. Two signed electrical setup sheets list different bias and mode settings. The run log identifies the specimen and contains complete exposure and event records, but contains no sheet identifier or revision link. Both setup sheets remain plausible; the supplied package contains no other linkage.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-583480","evidence_refs":["SF-381825","OBS-658379"],"reason":"CONFIGURATION_SCOPE_UNRESOLVED","requested_evidence":["RUN_TO_SETUP_REVISION_LINK"]}`



## RC12-D1-A

관측 누락이 아니라 실제 시간기록과 보고 문장의 모순이다. 종료 후 정상 복귀는 자극 중 변화가 없었다는 결론의 근거가 아니다. 정량 EMC 합격기준을 새로 지정하지 않는다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U217; configuration=RC12-C317; run=RC12-R417. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the report sentence agree with the time-aligned measurements? The acquisition coverage is complete.

**제안:** Describe the monitored channel as having remained at its pre-stimulus baseline throughout the stimulus.

**가상 관측:** Record scope: unit=RC12-U217; configuration=RC12-C317; run=RC12-R417. The continuous and time-aligned channel record shows a repeatable offset during each stimulus interval. It returns to baseline after the intervals. No acquisition gap or measurement-mapping ambiguity is reported.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-442996","evidence_refs":["SF-145154","OBS-204208"],"reason":"EVIDENCE_INTERPRETATION_ERROR"}`



## RC12-D1-B

관측 누락이 아니라 실제 시간기록과 보고 문장의 모순이다. 종료 후 정상 복귀는 자극 중 변화가 없었다는 결론의 근거가 아니다. 정량 EMC 합격기준을 새로 지정하지 않는다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U217; configuration=RC12-C317; run=RC12-R417. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the report sentence agree with the time-aligned measurements? The acquisition coverage is complete.

**제안:** Describe the monitored channel as having remained at its pre-stimulus baseline throughout the stimulus.

**가상 관측:** Record scope: unit=RC12-U217; configuration=RC12-C317; run=RC12-R417. The continuous and time-aligned channel record stays at its pre-stimulus baseline during each stimulus interval and afterward. No acquisition gap or measurement-mapping ambiguity is reported.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-442996","evidence_refs":["SF-145154","OBS-204208"]}`



## RC12-D2-A

측정은 이루어졌고 기록 내용이 제안을 지지·반박하는지만 바꾼다. 방법 구현 오류나 관측 범위 누락과 대비된다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U218; configuration=RC12-C318; run=RC12-R418. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the proposed description match the archived continuous channel stream for this interval?

**제안:** State that the archive contains no repeatable channel disturbance time-aligned with the applied excitation.

**가상 관측:** Record scope: unit=RC12-U218; configuration=RC12-C318; run=RC12-R418. The archive includes complete synchronized excitation and channel traces. It contains no repeatable channel step or excursion aligned with excitation in this interval.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-515909","evidence_refs":["SF-598337","OBS-745218"]}`



## RC12-D2-B

측정은 이루어졌고 기록 내용이 제안을 지지·반박하는지만 바꾼다. 방법 구현 오류나 관측 범위 누락과 대비된다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U218; configuration=RC12-C318; run=RC12-R418. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the proposed description match the archived continuous channel stream for this interval?

**제안:** State that the archive contains no repeatable channel disturbance time-aligned with the applied excitation.

**가상 관측:** Record scope: unit=RC12-U218; configuration=RC12-C318; run=RC12-R418. The archive includes complete synchronized excitation and channel traces. Repeated excitation onsets coincide with repeated channel steps, and the observations are explicitly retained in the run report.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-515909","evidence_refs":["SF-598337","OBS-745218"],"reason":"EVIDENCE_INTERPRETATION_ERROR"}`



## RC12-F1-A

형상이 무엇인지 몰라서가 아니라, 알려진 현재 형상에 C²를 적용할 선정근거가 없다. 다른 장비 값을 복사했다는 이유만으로 무조건 잘못된 수치라고 확정하지 않고 질문 범위의 근거를 요청한다.

**문헌 원리:** The coefficient C^2 in the semi-empirical force-limit relation depends on configuration and needs an adequate justification for its selection.

**위치:** Introduction following Eq. (1)

**가상 질문:** Review scope: unit=RC12-U211; configuration=RC12-C311; run=RC12-R411. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the choice of C^2 justified for the current load/support configuration? Input spectra, mass, modal data and as-tested identity are already available.

**제안:** Complete the coefficient-selection-basis check before accepting the proposed force-limit envelope.

**가상 관측:** Record scope: unit=RC12-U211; configuration=RC12-C311; run=RC12-R411. The selected coefficient is copied from a differently mounted load. The current mounting and load identities are known and documented, but the package includes no derivation or equivalence justification linking that choice to the current interface dynamics.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-351752","evidence_refs":["SF-463341","OBS-761608"],"reason":"FORCE_LIMIT_BASIS_UNRESOLVED","requested_evidence":["CURRENT_INTERFACE_C2_JUSTIFICATION"]}`



## RC12-F1-B

형상이 무엇인지 몰라서가 아니라, 알려진 현재 형상에 C²를 적용할 선정근거가 없다. 다른 장비 값을 복사했다는 이유만으로 무조건 잘못된 수치라고 확정하지 않고 질문 범위의 근거를 요청한다.

**문헌 원리:** The coefficient C^2 in the semi-empirical force-limit relation depends on configuration and needs an adequate justification for its selection.

**위치:** Introduction following Eq. (1)

**가상 질문:** Review scope: unit=RC12-U211; configuration=RC12-C311; run=RC12-R411. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the choice of C^2 justified for the current load/support configuration? Input spectra, mass, modal data and as-tested identity are already available.

**제안:** Complete the coefficient-selection-basis check before accepting the proposed force-limit envelope.

**가상 관측:** Record scope: unit=RC12-U211; configuration=RC12-C311; run=RC12-R411. The selected coefficient is accompanied by a documented derivation tied to the current load and support dynamics. The record explicitly identifies the current mounting and load, with stated assumptions and a sensitivity check.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-351752","evidence_refs":["SF-463341","OBS-761608"]}`



## RC12-F2-A

C² 숫자 존재와 선정 근거 존재를 구분한다. 단순 표준값 문구는 현재 형상에의 적용 근거가 아니며, 존재하는 근거의 정량 적정성을 이 문제에서 새로 승인하지 않는다.

**문헌 원리:** The coefficient C^2 in the semi-empirical force-limit relation depends on configuration and needs an adequate justification for its selection.

**위치:** Introduction following Eq. (1)

**가상 질문:** Review scope: unit=RC12-U212; configuration=RC12-C312; run=RC12-R412. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the engineering basis for selecting C^2 traceable in this record package? Other calculation inputs are complete.

**제안:** Complete the rationale check for the chosen semi-empirical coefficient.

**가상 관측:** Record scope: unit=RC12-U212; configuration=RC12-C312; run=RC12-R412. A coefficient value and the current test-article identifiers are filled in. The rationale links to an experience dataset or analysis with an explicit applicability argument for this configuration and records the selection decision.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-794340","evidence_refs":["SF-544938","OBS-135424"]}`



## RC12-F2-B

C² 숫자 존재와 선정 근거 존재를 구분한다. 단순 표준값 문구는 현재 형상에의 적용 근거가 아니며, 존재하는 근거의 정량 적정성을 이 문제에서 새로 승인하지 않는다.

**문헌 원리:** The coefficient C^2 in the semi-empirical force-limit relation depends on configuration and needs an adequate justification for its selection.

**위치:** Introduction following Eq. (1)

**가상 질문:** Review scope: unit=RC12-U212; configuration=RC12-C312; run=RC12-R412. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the engineering basis for selecting C^2 traceable in this record package? Other calculation inputs are complete.

**제안:** Complete the rationale check for the chosen semi-empirical coefficient.

**가상 관측:** Record scope: unit=RC12-U212; configuration=RC12-C312; run=RC12-R412. A coefficient value and the current test-article identifiers are filled in. The rationale field contains only the words standard choice. There is no referenced experience dataset, analysis or written justification for this configuration.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-794340","evidence_refs":["SF-544938","OBS-135424"],"reason":"FORCE_LIMIT_BASIS_UNRESOLVED","requested_evidence":["C2_SELECTION_DECISION_RECORD"]}`



## RC12-I1-A

입력이 없거나 모드를 식별하지 못한 문제가 아니다. 두 스펙트럼의 독립 최댓값을 사용하는 식과 다른 연산을 수행했으므로 방법 적용 오류다. 특정 평가 문제의 RMS·힘제어 사례를 가져오지 않았다.

**문헌 원리:** Equation (2) defines C^2 as the maximum interface-force PSD divided by the total load mass squared and the maximum interface-acceleration PSD. These two maxima need not occur at the same frequency.

**위치:** Section 2, Equation (2)

**가상 질문:** Review scope: unit=RC12-U205; configuration=RC12-C305; run=RC12-R405. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the described scalar reduction implement Equation (2) in the cited method? All required spectra and mass data are supplied. Check the calculation rule, not the numerical result.

**제안:** Use this reduction as an implementation of the cited equation for C^2.

**가상 관측:** Record scope: unit=RC12-U205; configuration=RC12-C305; run=RC12-R405. The force PSD and acceleration PSD attain their separate global maxima at different frequencies. The implementation takes the maximum force PSD but uses the acceleration PSD at that force-peak frequency in the denominator, even though it is smaller than the maximum acceleration PSD. The measured mass is squared in the denominator.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-803322","evidence_refs":["SF-851742","OBS-435221"],"reason":"METHOD_INTERPRETATION_ERROR"}`



## RC12-I1-B

입력이 없거나 모드를 식별하지 못한 문제가 아니다. 두 스펙트럼의 독립 최댓값을 사용하는 식과 다른 연산을 수행했으므로 방법 적용 오류다. 특정 평가 문제의 RMS·힘제어 사례를 가져오지 않았다.

**문헌 원리:** Equation (2) defines C^2 as the maximum interface-force PSD divided by the total load mass squared and the maximum interface-acceleration PSD. These two maxima need not occur at the same frequency.

**위치:** Section 2, Equation (2)

**가상 질문:** Review scope: unit=RC12-U205; configuration=RC12-C305; run=RC12-R405. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the described scalar reduction implement Equation (2) in the cited method? All required spectra and mass data are supplied. Check the calculation rule, not the numerical result.

**제안:** Use this reduction as an implementation of the cited equation for C^2.

**가상 관측:** Record scope: unit=RC12-U205; configuration=RC12-C305; run=RC12-R405. The force PSD and acceleration PSD attain their separate global maxima at different frequencies. The implementation uses the separate maximum of each spectrum and divides the force maximum by the measured mass squared times the acceleration maximum.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-803322","evidence_refs":["SF-851742","OBS-435221"]}`



## RC12-I2-A

질량값·스펙트럼은 있고 질량의 지수만 다르다. 데이터 해석이나 선정근거 부족이 아니라 명시된 식을 구현한 방법의 일치 여부를 판단한다.

**문헌 원리:** Equation (2) defines C^2 as the maximum interface-force PSD divided by the total load mass squared and the maximum interface-acceleration PSD. These two maxima need not occur at the same frequency.

**위치:** Section 2, Equation (2)

**가상 질문:** Review scope: unit=RC12-U206; configuration=RC12-C306; run=RC12-R406. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the stated mass dependence match Equation (2) of the cited reduction? Input quantities and their units are known.

**제안:** Accept the described reduction as algebraically consistent with the cited equation for C^2.

**가상 관측:** Record scope: unit=RC12-U206; configuration=RC12-C306; run=RC12-R406. The implementation uses the separate maxima of the force and acceleration PSDs. Its denominator contains the measured total mass squared multiplied by the acceleration maximum. Consistent units are used throughout.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-352731","evidence_refs":["SF-760161","OBS-177897"]}`



## RC12-I2-B

질량값·스펙트럼은 있고 질량의 지수만 다르다. 데이터 해석이나 선정근거 부족이 아니라 명시된 식을 구현한 방법의 일치 여부를 판단한다.

**문헌 원리:** Equation (2) defines C^2 as the maximum interface-force PSD divided by the total load mass squared and the maximum interface-acceleration PSD. These two maxima need not occur at the same frequency.

**위치:** Section 2, Equation (2)

**가상 질문:** Review scope: unit=RC12-U206; configuration=RC12-C306; run=RC12-R406. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the stated mass dependence match Equation (2) of the cited reduction? Input quantities and their units are known.

**제안:** Accept the described reduction as algebraically consistent with the cited equation for C^2.

**가상 관측:** Record scope: unit=RC12-U206; configuration=RC12-C306; run=RC12-R406. The implementation uses the separate maxima of the force and acceleration PSDs. Its denominator contains the measured total mass to the first power multiplied by the acceleration maximum. It labels that result C^2; no other mass factor or unit conversion is applied.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-352731","evidence_refs":["SF-760161","OBS-177897"],"reason":"METHOD_INTERPRETATION_ERROR"}`



## RC12-L1-A

모달 입력 항목 중 잔여질량만 누락시킨다. 추정값을 임의로 채우지 않고 그 항목을 요청하며, 제공됐을 때는 입력 존재 검사만 종료한다.

**문헌 원리:** The stated CSMA load description includes total mass, fixed-interface natural frequencies, modal effective and residual masses, damping, and translational apparent-mass information.

**위치:** Section 4.1.1 Mathematical model

**가상 질문:** Review scope: unit=RC12-U209; configuration=RC12-C309; run=RC12-R409. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the listed load-model input package complete for residual-mass terms in the cited CSMA formulation? Damping and other listed inputs are available.

**제안:** Complete this load-input availability check before running the coupled model.

**가상 관측:** Record scope: unit=RC12-U209; configuration=RC12-C309; run=RC12-R409. Total mass, fixed-interface frequencies, modal effective masses, damping and translational apparent-mass data are supplied. The residual-mass terms are absent. The package states that the retained-mode data do not permit these missing terms to be recovered.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-947496","evidence_refs":["SF-684912","OBS-171408"],"reason":"MODAL_INPUTS_MISSING","requested_evidence":["RESIDUAL_MASS_TERMS"]}`



## RC12-L1-B

모달 입력 항목 중 잔여질량만 누락시킨다. 추정값을 임의로 채우지 않고 그 항목을 요청하며, 제공됐을 때는 입력 존재 검사만 종료한다.

**문헌 원리:** The stated CSMA load description includes total mass, fixed-interface natural frequencies, modal effective and residual masses, damping, and translational apparent-mass information.

**위치:** Section 4.1.1 Mathematical model

**가상 질문:** Review scope: unit=RC12-U209; configuration=RC12-C309; run=RC12-R409. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the listed load-model input package complete for residual-mass terms in the cited CSMA formulation? Damping and other listed inputs are available.

**제안:** Complete this load-input availability check before running the coupled model.

**가상 관측:** Record scope: unit=RC12-U209; configuration=RC12-C309; run=RC12-R409. Total mass, fixed-interface frequencies, modal effective masses, damping and translational apparent-mass data are supplied. Direction-specific residual-mass terms are also tabulated and mapped to the load configuration.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-947496","evidence_refs":["SF-684912","OBS-171408"]}`



## RC12-L2-A

감쇠 가정 자체가 없는 것과 감쇠값의 정확도를 검증하지 못한 것은 다르다. 여기서는 전자에만 자료 요청을 붙인다.

**문헌 원리:** The stated CSMA load description includes total mass, fixed-interface natural frequencies, modal effective and residual masses, damping, and translational apparent-mass information.

**위치:** Section 4.1.1 Mathematical model

**가상 질문:** Review scope: unit=RC12-U210; configuration=RC12-C310; run=RC12-R410. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the required modal damping inputs available for the cited load model? Check availability, not the correctness of the damping magnitudes.

**제안:** Complete the modal-input checklist for this calculation package.

**가상 관측:** Record scope: unit=RC12-U210; configuration=RC12-C310; run=RC12-R410. The package contains total mass, fixed-interface frequencies, effective and residual masses, and apparent-mass information. It also assigns a measured or justified assumed damping ratio to each modeled mode.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-705995","evidence_refs":["SF-579701","OBS-383983"]}`



## RC12-L2-B

감쇠 가정 자체가 없는 것과 감쇠값의 정확도를 검증하지 못한 것은 다르다. 여기서는 전자에만 자료 요청을 붙인다.

**문헌 원리:** The stated CSMA load description includes total mass, fixed-interface natural frequencies, modal effective and residual masses, damping, and translational apparent-mass information.

**위치:** Section 4.1.1 Mathematical model

**가상 질문:** Review scope: unit=RC12-U210; configuration=RC12-C310; run=RC12-R410. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the required modal damping inputs available for the cited load model? Check availability, not the correctness of the damping magnitudes.

**제안:** Complete the modal-input checklist for this calculation package.

**가상 관측:** Record scope: unit=RC12-U210; configuration=RC12-C310; run=RC12-R410. The package contains total mass, fixed-interface frequencies, effective and residual masses, and apparent-mass information. The damping-assignment table is absent and no damping assumptions are recorded elsewhere.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-705995","evidence_refs":["SF-579701","OBS-383983"],"reason":"MODAL_INPUTS_MISSING","requested_evidence":["MODAL_DAMPING_ASSIGNMENT"]}`



## RC12-O1-A

관측했지만 해석을 잘못한 경우가 아니라, 문제의 구간을 관측하지 않았다. 전체 구간 관측을 주장하는 proposal에 대한 검토이므로 자료 요청 action으로 기계적으로 바꾸지 않는다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U215; configuration=RC12-C315; run=RC12-R415. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does this package actually document observation of the channel throughout the applied disturbance? Check observation coverage, not a numerical acceptance threshold.

**제안:** Describe this package as containing channel monitoring throughout the disturbance interval.

**가상 관측:** Record scope: unit=RC12-U215; configuration=RC12-C315; run=RC12-R415. The clock and stimulus log are aligned. Channel readings were taken immediately before and after the disturbance, but the acquisition system was disabled for the entire disturbance interval. No measurement of that interval exists.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-669944","evidence_refs":["SF-837620","OBS-810191"],"reason":"MONITORING_COVERAGE_INSUFFICIENT"}`



## RC12-O1-B

관측했지만 해석을 잘못한 경우가 아니라, 문제의 구간을 관측하지 않았다. 전체 구간 관측을 주장하는 proposal에 대한 검토이므로 자료 요청 action으로 기계적으로 바꾸지 않는다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U215; configuration=RC12-C315; run=RC12-R415. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does this package actually document observation of the channel throughout the applied disturbance? Check observation coverage, not a numerical acceptance threshold.

**제안:** Describe this package as containing channel monitoring throughout the disturbance interval.

**가상 관측:** Record scope: unit=RC12-U215; configuration=RC12-C315; run=RC12-R415. The clock and stimulus log are aligned. Channel acquisition spans the complete disturbance interval as well as the before-and-after reference intervals. The acquisition log shows no gap in coverage.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-669944","evidence_refs":["SF-837620","OBS-810191"]}`



## RC12-O2-A

다른 시간의 데이터가 정상이더라도 비관측 구간의 상태는 확인되지 않는다. 시험의 합격·불합격이 아니라 전체 구간 관측을 입증하는지에 한정한다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U216; configuration=RC12-C316; run=RC12-R416. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the acquisition record substantiate continuous coverage of the channel during the specified stimulus sequence?

**제안:** Use this package as evidence of complete channel observation during the specified stimulus sequence.

**가상 관측:** Record scope: unit=RC12-U216; configuration=RC12-C316; run=RC12-R416. The intended channels are identified and the samples are valid. The recorder-status log and timestamps cover every pulse group without gaps; the continuous stream is linked to the stimulus sequence.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-671691","evidence_refs":["SF-976544","OBS-876075"]}`



## RC12-O2-B

다른 시간의 데이터가 정상이더라도 비관측 구간의 상태는 확인되지 않는다. 시험의 합격·불합격이 아니라 전체 구간 관측을 입증하는지에 한정한다.

**문헌 원리:** The report evaluates channel data during interference injection against baseline data before and after testing, and examines response timing in relation to the applied sweep.

**위치:** 1.6 Pass/Fail criteria

**가상 질문:** Review scope: unit=RC12-U216; configuration=RC12-C316; run=RC12-R416. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the acquisition record substantiate continuous coverage of the channel during the specified stimulus sequence?

**제안:** Use this package as evidence of complete channel observation during the specified stimulus sequence.

**가상 관측:** Record scope: unit=RC12-U216; configuration=RC12-C316; run=RC12-R416. The intended channels are identified and the available samples are valid. A recorder-status log identifies an acquisition gap covering one complete pulse group. No backup channel data cover that missing interval.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-671691","evidence_refs":["SF-976544","OBS-876075"],"reason":"MONITORING_COVERAGE_INSUFFICIENT"}`



## RC12-P1-A

센서 coverage나 노출 메타데이터가 아닌 열원 크기의 입력 누락이다. 전체 입력을 임의 비율로 분할하는 가정은 넣지 않는다.

**문헌 원리:** Individual component power estimates were weakened by shared power buses and long measurement leads. The report emphasizes knowing both dissipation rates and heat-source locations for correlation.

**위치:** On-Site Thermal Support; Conclusions

**가상 질문:** Review scope: unit=RC12-U213; configuration=RC12-C313; run=RC12-R413. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the component heat-source powers available for the stated operating mode? Heat-source locations and configuration identity are already mapped.

**제안:** Complete the component heat-input availability check for this operating mode.

**가상 관측:** Record scope: unit=RC12-U213; configuration=RC12-C313; run=RC12-R413. All heat-source locations and component identifiers are mapped. Only the assembly input-current record is supplied. There are no component-level dissipated powers or a power-allocation model for this mode in the package.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-621655","evidence_refs":["SF-174855","OBS-530170"],"reason":"POWER_DISSIPATION_UNRESOLVED","requested_evidence":["MODE_SPECIFIC_COMPONENT_DISSIPATIONS"]}`



## RC12-P1-B

센서 coverage나 노출 메타데이터가 아닌 열원 크기의 입력 누락이다. 전체 입력을 임의 비율로 분할하는 가정은 넣지 않는다.

**문헌 원리:** Individual component power estimates were weakened by shared power buses and long measurement leads. The report emphasizes knowing both dissipation rates and heat-source locations for correlation.

**위치:** On-Site Thermal Support; Conclusions

**가상 질문:** Review scope: unit=RC12-U213; configuration=RC12-C313; run=RC12-R413. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the component heat-source powers available for the stated operating mode? Heat-source locations and configuration identity are already mapped.

**제안:** Complete the component heat-input availability check for this operating mode.

**가상 관측:** Record scope: unit=RC12-U213; configuration=RC12-C313; run=RC12-R413. All heat-source locations and component identifiers are mapped. The package also tabulates the component-level dissipated powers for this mode, including the stated loss allocation and a reconciliation to the assembly record.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-621655","evidence_refs":["SF-174855","OBS-530170"]}`



## RC12-P2-A

측정 온도와 계산 온도의 대응 문제가 아니라 발열 입력의 공간 배치 누락이다. 위치표가 있으면 준비상태만 확인하며 열모델 상관 결과를 승인하지 않는다.

**문헌 원리:** Individual component power estimates were weakened by shared power buses and long measurement leads. The report emphasizes knowing both dissipation rates and heat-source locations for correlation.

**위치:** On-Site Thermal Support; Conclusions

**가상 질문:** Review scope: unit=RC12-U214; configuration=RC12-C314; run=RC12-R414. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Can each recorded dissipation be assigned to its physical heat-source location in the thermal model? Review the heat-input mapping record only.

**제안:** Complete the thermal heat-source input checklist before correlation.

**가상 관측:** Record scope: unit=RC12-U214; configuration=RC12-C314; run=RC12-R414. Component dissipated powers and operating modes are tabulated and linked to this configuration. An allocation table links every sheet identifier to its physical component and corresponding thermal-model node.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-791999","evidence_refs":["SF-188880","OBS-722888"]}`



## RC12-P2-B

측정 온도와 계산 온도의 대응 문제가 아니라 발열 입력의 공간 배치 누락이다. 위치표가 있으면 준비상태만 확인하며 열모델 상관 결과를 승인하지 않는다.

**문헌 원리:** Individual component power estimates were weakened by shared power buses and long measurement leads. The report emphasizes knowing both dissipation rates and heat-source locations for correlation.

**위치:** On-Site Thermal Support; Conclusions

**가상 질문:** Review scope: unit=RC12-U214; configuration=RC12-C314; run=RC12-R414. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Can each recorded dissipation be assigned to its physical heat-source location in the thermal model? Review the heat-input mapping record only.

**제안:** Complete the thermal heat-source input checklist before correlation.

**가상 관측:** Record scope: unit=RC12-U214; configuration=RC12-C314; run=RC12-R414. Component dissipated powers and operating modes are tabulated and linked to this configuration. The identifiers on the power sheet cannot be linked to the physical components or thermal nodes. No allocation or location map is supplied.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-791999","evidence_refs":["SF-188880","OBS-722888"],"reason":"POWER_DISSIPATION_UNRESOLVED","requested_evidence":["HEAT_SOURCE_TO_MODEL_LOCATION_MAP"]}`



## RC12-Q1-A

경계 입력은 명시적으로 주어져 있으며 직접적인 차이는 측정 대상과 공간 집계다. 단위가 같은 온도값도 대응관계가 다르면 직접 비교를 반박한다.

**문헌 원리:** Calculated television-camera temperatures represented average case temperatures, whereas internal thermocouples measured heater temperatures for which corresponding models were absent.

**위치:** Canister Correlations

**가상 질문:** Review scope: unit=RC12-U207; configuration=RC12-C307; run=RC12-R407. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the reported temperature represent the same spatial quantity as the model output used in this comparison?

**제안:** Compare the reported temperature directly with the modeled casing-average temperature.

**가상 관측:** Record scope: unit=RC12-U207; configuration=RC12-C307; run=RC12-R407. The reported channel is a single internal actuator-heater junction measurement. The model output averages the outer casing surface. No transfer model maps the heater junction to the casing average; boundary inputs and timing are otherwise documented.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-365135","evidence_refs":["SF-579303","OBS-356935"],"reason":"MEASUREMENT_MAPPING_MISMATCH"}`



## RC12-Q1-B

경계 입력은 명시적으로 주어져 있으며 직접적인 차이는 측정 대상과 공간 집계다. 단위가 같은 온도값도 대응관계가 다르면 직접 비교를 반박한다.

**문헌 원리:** Calculated television-camera temperatures represented average case temperatures, whereas internal thermocouples measured heater temperatures for which corresponding models were absent.

**위치:** Canister Correlations

**가상 질문:** Review scope: unit=RC12-U207; configuration=RC12-C307; run=RC12-R407. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Does the reported temperature represent the same spatial quantity as the model output used in this comparison?

**제안:** Compare the reported temperature directly with the modeled casing-average temperature.

**가상 관측:** Record scope: unit=RC12-U207; configuration=RC12-C307; run=RC12-R407. The reported channel is a weighted aggregate of outer-casing surface measurements. The model output uses the same locations and weights for its casing average. Boundary inputs and timing are documented.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-365135","evidence_refs":["SF-579303","OBS-356935"]}`



## RC12-Q2-A

최댓값과 평균의 공간 집계 대상이 다른 상황이다. RMS 연산 오류 사례와 다르게 여기서는 각 통계량 자체가 잘못 계산됐다고 하지 않고 대응관계만 검토한다.

**문헌 원리:** Calculated television-camera temperatures represented average case temperatures, whereas internal thermocouples measured heater temperatures for which corresponding models were absent.

**위치:** Canister Correlations

**가상 질문:** Review scope: unit=RC12-U208; configuration=RC12-C308; run=RC12-R408. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the measurement-to-model mapping consistent for the stated surface-temperature statistic? Check mapping only.

**제안:** Use the reported surface statistic as the directly corresponding measurement for the model statistic.

**가상 관측:** Record scope: unit=RC12-U208; configuration=RC12-C308; run=RC12-R408. The model statistic is an area-weighted average over six casing regions. The reported statistic applies the same six region weights to the corresponding calibrated, time-aligned surface measurements.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-230763","evidence_refs":["SF-637110","OBS-317805"]}`



## RC12-Q2-B

최댓값과 평균의 공간 집계 대상이 다른 상황이다. RMS 연산 오류 사례와 다르게 여기서는 각 통계량 자체가 잘못 계산됐다고 하지 않고 대응관계만 검토한다.

**문헌 원리:** Calculated television-camera temperatures represented average case temperatures, whereas internal thermocouples measured heater temperatures for which corresponding models were absent.

**위치:** Canister Correlations

**가상 질문:** Review scope: unit=RC12-U208; configuration=RC12-C308; run=RC12-R408. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the measurement-to-model mapping consistent for the stated surface-temperature statistic? Check mapping only.

**제안:** Use the reported surface statistic as the directly corresponding measurement for the model statistic.

**가상 관측:** Record scope: unit=RC12-U208; configuration=RC12-C308; run=RC12-R408. The model statistic is an area-weighted average over six casing regions. The reported statistic is the temperature of only the hottest sampled region. Both are time-aligned and calibrated, but there is no mapping from that maximum-region statistic to the surface average.

**AI 정답 후보:** `{"action":"CHALLENGE","claim_id":"CLM-230763","evidence_refs":["SF-637110","OBS-317805"],"reason":"MEASUREMENT_MAPPING_MISMATCH"}`



## RC12-X1-A

이벤트 수·설정 기록과 입자 노출량은 별개다. 이 쌍은 fluence의 가용성만 바꾸며, 자료가 없다는 이유로 모니터링 자체가 없었다고 판단하지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U203; configuration=RC12-C303; run=RC12-R403. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the run-integrated particle fluence available? The electrical operating configuration and event-monitoring coverage are established; do not assess event susceptibility.

**제안:** Complete the exposure-data availability check for this irradiation interval.

**가상 관측:** Record scope: unit=RC12-U203; configuration=RC12-C303; run=RC12-R403. The run package identifies the ion and geometry and includes electrical settings and continuous event monitoring. The integrated particle fluence is not recorded, and no calibrated beam history permitting its reconstruction is available.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-207765","evidence_refs":["SF-664925","OBS-600103"],"reason":"EXPOSURE_METADATA_UNRESOLVED","requested_evidence":["RUN_INTEGRATED_FLUENCE"]}`



## RC12-X1-B

이벤트 수·설정 기록과 입자 노출량은 별개다. 이 쌍은 fluence의 가용성만 바꾸며, 자료가 없다는 이유로 모니터링 자체가 없었다고 판단하지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U203; configuration=RC12-C303; run=RC12-R403. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Is the run-integrated particle fluence available? The electrical operating configuration and event-monitoring coverage are established; do not assess event susceptibility.

**제안:** Complete the exposure-data availability check for this irradiation interval.

**가상 관측:** Record scope: unit=RC12-U203; configuration=RC12-C303; run=RC12-R403. The run package identifies the ion and geometry and includes electrical settings and continuous event monitoring. A beam-log entry supplies the integrated particle fluence and is linked to the same run interval.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-207765","evidence_refs":["SF-664925","OBS-600103"]}`



## RC12-X2-A

전기적 조건은 충분한 상태로 유지한다. 이온·입사 형상은 노출 메타데이터이며, 여기서는 LET 변환이나 이벤트 단면적을 계산하지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U204; configuration=RC12-C304; run=RC12-R404. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the ion identity and incidence geometry recorded for this run? Limit the check to the exposure record.

**제안:** Complete the exposure-record checklist before combining this result with other runs.

**가상 관측:** Record scope: unit=RC12-U204; configuration=RC12-C304; run=RC12-R404. Electrical settings, integrated fluence and event logs are linked to the run. The exposure sheet names the ion species and incidence geometry, and the facility entry links those fields to this interval.

**AI 정답 후보:** `{"action":"NO_ACTION_REQUIRED","claim_id":"CLM-976879","evidence_refs":["SF-583023","OBS-300335"]}`



## RC12-X2-B

전기적 조건은 충분한 상태로 유지한다. 이온·입사 형상은 노출 메타데이터이며, 여기서는 LET 변환이나 이벤트 단면적을 계산하지 않는다.

**문헌 원리:** The data requirements retain SET/SEL counts and monitored signals together with facility and electrical information, including flux, fluence, LET, ion, geometry and electrical setup.

**위치:** 8 Data Requirements

**가상 질문:** Review scope: unit=RC12-U204; configuration=RC12-C304; run=RC12-R404. Only records matching all three scope identifiers may substantiate this check; any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. Are the ion identity and incidence geometry recorded for this run? Limit the check to the exposure record.

**제안:** Complete the exposure-record checklist before combining this result with other runs.

**가상 관측:** Record scope: unit=RC12-U204; configuration=RC12-C304; run=RC12-R404. Electrical settings, integrated fluence and event logs are linked to the run. The ion-species field and incidence-angle field are blank. No beamline geometry sheet or facility entry resolves those fields.

**AI 정답 후보:** `{"action":"REQUEST_EVIDENCE","claim_id":"CLM-976879","evidence_refs":["SF-583023","OBS-300335"],"reason":"EXPOSURE_METADATA_UNRESOLVED","requested_evidence":["ION_AND_INCIDENCE_GEOMETRY"]}`

