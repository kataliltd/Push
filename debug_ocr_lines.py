#!/usr/bin/env python3
"""
Debug script to see what lines contain potential delivery items
"""

import re

# Sample from the user's OCR text - page 2 (should have ~11-12 items)
page2_text = """6 tsc1152169H wsFo18 CCMT O9T3O8-SM INSERT GRADE IC9O7 M12-7
2 sHR0850530E wsF185 M16x2 HSS SPIML F}oINT MAC}JINETAP AB02-1
30 PMT1204568V wsF572 SOUARESHOULDER SOMT 09r308-M:M8330 sso09 & MILL CHAMFER AD03-6
3 .V PMT1201013J wsF196 TNMG 16O4O4E-FF INSERT GMDET843O AD10-1
1 ATG9613442c wsF487 ELTE PALM COATEDI(W GLOVES SZ.8 34.274 MAXIFLEX AE05-3
- 2 scH2450001A wsF421 Radial Bristle Brush A Type BB-ZB1 2.52x1 7y25.4mm P80 with Adapt AH06-2
\\r 14 Isc1152652K wsF506 FFQs SZMU 12O52OHP INSERT GRADEIC88z MEZZCAs
v3 rsc1152969P WSF149 1 20412-M3M TNSERT GRADEtc6o2s SNMG ME72FM
8 tsc1316880P MEZZFM
1 Y lscl 152612F wsF429 WSF456 TAG N3J INSERT GMDE IC8O8
1',l, 1sc1141379H wsF519 CNMG O9O4O8-M3M INSERT GMDEtC6O25 MEZZ-EC2
3 AVN8301236K wsF428 BUBBLE WMPROIL SMALL BUBBLES 900mmx100M oFFtCE/C"""

# Page 3 (should have 12 items)
page3_text = """--\\- rz tscl 152226W wsrsz+ / CNMG 120408-M3M INSERT GRADEIC6O2S AA07-1
AA12-7 €
-+\" 1 tsc1152169H WSFO18 CCMT O9T3O8.SM INI}ERT GRADE IC9O7
12
-\\ rsc1316880N wsF491 TAG N3J INSERT GRADE IC8O7 4806-7 €
AD10-1
.+1 tND1073430K wsF289 SO16 INSERT SCREW
AD10-1
{r PMT1201013J wsF196 TNMG 16O4O4E-FF IIISERT GRADETE43O
TAG N3J INSERT GRADE IC83O AK06-1 +_-
Y28 tsc1316880R WSFa46 1
-\\z 1sc1152969P WSF149 SNMG 120412.M3M INSERT GMDEIC6O25 METZFAi 4-
MEZZ-CF3
-\\'s 1sc1152226Y wsF529 CNMG 120408.M3M INSERT GRADEICSOo
ft+ ATG96134421
-L1 lscl 141379H WSF489 WSF519 34-274MMIFLEX ELITE PALM COATEDK^^/ GLOVES SZ.1O"""

# Page 4 (should have ~20 items)
page4_text = """10 HRN1208800G wsF573 S1OO.O3OO.E2 INSERT GRADE TF45 ACl3-2
1 tsc12145207D wsF541 TNMG 16O4O8E-NF INSERT GRADETs43O ADO14
3 DOR1615770A wsF510 S770HB 't0.00mm CARBIDE AICrN FLATSHORT sFL END MILL U NEQUAL AD03-6
1 KM11641896V7 wsF494 GOPR4CH,I6OORO32HBM KCU2O GOMILLPRo END MILL AD03-6
1 PMT1201010Mt0 wsF522 SCMT O9T3O8E-FM2 INSERT GMDET843O AD03-6 .--
10 PMT1204568V wsF572 09T308-M:M8330 SOUARESHOULDEr ILLm HAMFER & c sso09 SOMT AE0S-3 _
5 ATG9613442G wsF487 34-274MMIFLEX ELITE PALM COATEDKM/ GLOVES SZ'8 AS08-2 -
2 HAL96'14183A wsF540 cLovEs DlsposABLE BLUE NlrRlLE3.sG (PK-100) (sz.M)
3 tsc12125307 WSFo97 22ER 4.OO ISo THREADING II'ISERTGRADE ICgOA ME7Z.CA5
2 tscl 152969P wsF149 SNMG 120412.M3M INSERT GRADEtC6O25 ME7zFM --
38 tsc1316880P wsF429 TAG N3J INSERT GMDE IC8O8 ME72
6 so19522550H wsF40't RPE ROLLS 50m PERROLL PL 2 BLUE (375-5HTS) CENTREFEED
2 HA19614105A wsF019 GLOVES DlsposABLE BLUE NlrRlLE 5G(PK-100) (sz-xL) MEZZ-AA2
5 rsc1152612F wsF456 DNMG 110404-M3M INSERT GRADEtC6O2S MEZZ-CA2
4 1sc1152226Y wsF529 CNMG 120408-M3M INSERT GRADEtC8O6 MEZZ-oF3
3 AVN9560400K wsF492 BROWN HANK 40-50mm SLEEVING-2SMREEL MEZZ-EA1
2 csP9590931Y wsF085 AURA 9322+ VALVED DUST/MIST RESPIMTor FFP2 (SGL) ME7Z.LD1"""

print("=" * 80)
print("PAGE 2 ANALYSIS")
print("=" * 80)
lines_p2 = page2_text.split('\n')
print(f"Total lines: {len(lines_p2)}")
for i, line in enumerate(lines_p2, 1):
    # Try to match pattern
    # Look for: [optional symbols] [digits] [optional symbols] [space] [part number pattern]
    match = re.search(r'(\d{1,3})\s+([A-Za-z0-9]+\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9]+)', line)
    if match:
        print(f"✓ Line {i}: QTY={match.group(1)}, PN={match.group(2)}, Code={match.group(3)}")
    else:
        print(f"✗ Line {i}: NO MATCH - {line[:60]}")

print("\n" + "=" * 80)
print("PAGE 3 ANALYSIS (with multi-line format)")
print("=" * 80)
lines_p3 = page3_text.split('\n')
print(f"Total lines: {len(lines_p3)}")
for i, line in enumerate(lines_p3, 1):
    match = re.search(r'(\d{1,3})\s+([A-Za-z0-9]+\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9]+)', line)
    if match:
        print(f"✓ Line {i}: QTY={match.group(1)}, PN={match.group(2)}, Code={match.group(3)}")
    elif line.strip().isdigit():
        print(f"? Line {i}: LONE QUANTITY: {line.strip()}")
    elif len(line.strip()) > 5:
        print(f"✗ Line {i}: NO MATCH - {line[:60]}")

print("\n" + "=" * 80)
print("PAGE 4 ANALYSIS")
print("=" * 80)
lines_p4 = page4_text.split('\n')
print(f"Total lines: {len(lines_p4)}")
for i, line in enumerate(lines_p4, 1):
    match = re.search(r'(\d{1,3})\s+([A-Za-z0-9]+\d{5,}[A-Za-z0-9]*)\s+([A-Za-z0-9]+)', line)
    if match:
        print(f"✓ Line {i}: QTY={match.group(1)}, PN={match.group(2)}, Code={match.group(3)}")
    else:
        print(f"✗ Line {i}: NO MATCH - {line[:60]}")
