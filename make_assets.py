# === ONE cell (Colab or GitHub Actions) ==========================================================================
# Builds the picture assets THE SAME WAY the app does (SeeData.java + GoogleImage.java), but on the computer, ahead of time. NO checking.
#   word list + search words   <- SeeData.java      (4th part of a word line = its own search words)
#   search words rule          <- GoogleImage.java  queryFor():  1) SeeData search words  2) FIX name table  3) word + chapter kind ("banana fruit")
#   search + pictures          <- Bing Images, first results, the FIRST 4 pictures that download (in search order), shrunk to 640 px JPEG
#   chapter by chapter         <- like downloadChapter(): all words of one chapter are searched + downloaded at the same time, then the next chapter
#   result                     -> every word: assets/<chapter>/english_odia_hindi.webp  (4 pictures merged 2x2)  ->  assets.zip
# If SeeData.java / GoogleImage.java are next to this script they are READ (always in sync with the app). If not, the copy built into this file is used.
# Re-run: words that already have their pictures are skipped, only unfinished words are downloaded again.  FRESH = True starts from zero.
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], check=False)

import io, os, re, time, csv, json, random, shutil, zipfile, hashlib, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

SEE_JAVA, GOOGLE_JAVA = "SeeData.java", "GoogleImage.java"
FRESH = False            # True = ignore old results and download everything again
REDO = []                # english names to download again, e.g. ["apple", "rose"]
GRID = 4                 # pictures per word (2 x 2)            (same as GoogleImage.GRID)
CANDIDATES = 14          # first search results that may be used per Bing page   (same as GoogleImage.CANDIDATES)
MAX_PAGES = 3            # only if fewer than 4 pictures could be downloaded from page 1: the next Bing pages are used too
STORE_PX = 640           # picture shrunk to this longest side, JPEG 82   (same as GoogleImage)
MIN_SIDE = 60            # smaller pictures are not used                  (same as GoogleImage)
WORD_WORKERS = 24        # words of one chapter downloaded at the same time
IMG_WORKERS = 96         # picture downloads at the same time
SEARCH_PARALLEL = 8      # Bing search pages requested at the same time
TILE, QUALITY = 300, 50  # merged WebP: 4 tiles of 300 px = 600 x 600, small files
OUT, STATE_FILE, REPORT = "assets", "state.json", "report.csv"
PAGE_STEP = 35           # Bing 'first=' step between result pages

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ---------------- built-in copy of SeeData.java (chapter|english|odia|hindi|search words) ----------------
DATA = """
07_Colors|black|କଳା|काला|
07_Colors|blue|ନୀଳ|नीला|
07_Colors|brown|ବାଦାମୀ|भूरा|
07_Colors|golden|ସୁନେଲି|सुनहरा|golden color
07_Colors|gray|ଧୂସର|स्लेटी|gray color
07_Colors|green|ସବୁଜ|हरा|
07_Colors|navy blue|ଗାଢ଼ ନୀଳ|गहरा नीला|
07_Colors|orange|କମଳା|नारंगी|
07_Colors|pink|ଗୋଲାପି|गुलाबी|
07_Colors|red|ନାଲି|लाल|
07_Colors|violet|ବାଇଗଣୀ|बैंगनी|
07_Colors|white|ଧଳା|सफेद|
07_Colors|yellow|ହଳଦିଆ|पीला|
07_Colors|maroon|ମାରୁନ|मरून|
07_Colors|sky blue|ଆକାଶୀ ନୀଳ|आसमानी|
07_Colors|light blue|ହାଲୁକା ନୀଳ|हल्का नीला|
07_Colors|light green|ହାଲୁକା ସବୁଜ|हल्का हरा|
07_Colors|dark green|ଗାଢ଼ ସବୁଜ|गहरा हरा|
07_Colors|silver|ରୂପେଲି|रुपहला|
07_Colors|cream|କ୍ରିମ|क्रीम|
07_Colors|beige|ବେଜ|बेज|
07_Colors|turquoise|ଫିରୋଜା|फ़िरोज़ी|
07_Colors|lavender|ଲ୍ୟାଭେଣ୍ଡର|लैवेंडर|lavender color
07_Colors|peach|ପିଚ୍|पीच|peach color
07_Colors|magenta|ମେଜେଣ୍ଟା|मैजेंटा|
07_Colors|coral|କୋରାଲ|मूंगा|coral color
07_Colors|mustard|ସୋରିଷ ରଙ୍ଗ|सरसों|mustard yellow color
07_Colors|olive green|ଅଲିଭ ସବୁଜ|जैतूनी हरा|
07_Colors|bronze|ବ୍ରୋଞ୍ଜ|काँस्य|bronze color
07_Colors|rainbow|ଇନ୍ଦ୍ରଧନୁ|इंद्रधनुष|rainbow colors
07_Colors|multicolor|ବହୁରଙ୍ଗୀ|बहुरंगी|multicolor colorful
08_Shapes|circle|ବୃତ୍ତ|वृत्त|
08_Shapes|cone|ଶଙ୍କୁ|शंकु|
08_Shapes|octagon|ଅଷ୍ଟଭୁଜ|अष्टभुज|
08_Shapes|cube|ଘନ|घन|
08_Shapes|cylinder|ସ୍ତମ୍ଭ|बेलन|
08_Shapes|hexagon|ଷଡ଼ଭୁଜ|षट्भुज|
08_Shapes|oval|ଅଣ୍ଡାକାର|अंडाकार|
08_Shapes|pentagon|ପଞ୍ଚଭୁଜ|पंचभुज|
08_Shapes|prism|ପ୍ରିଜ୍ମ|प्रिज्म|
08_Shapes|rectangle|ଆୟତ|आयत|
08_Shapes|rhombus|ସମଚତୁର୍ଭୁଜ|समचतुर्भुज|
08_Shapes|square|ବର୍ଗ|वर्ग|
08_Shapes|triangle|ତ୍ରିଭୁଜ|त्रिभुज|
08_Shapes|heart|ହୃଦୟ|दिल|heart shape
08_Shapes|star|ତାରା|तारा|star shape
08_Shapes|crescent|ଅର୍ଦ୍ଧଚନ୍ଦ୍ର|अर्धचंद्र|crescent shape
08_Shapes|sphere|ଗୋଲକ|गोला|sphere 3d shape
08_Shapes|pyramid|ପିରାମିଡ୍|पिरामिड|pyramid 3d shape
08_Shapes|trapezium|ସମଲମ୍ବ ଚତୁର୍ଭୁଜ|समलंब चतुर्भुज|trapezium shape geometry
08_Shapes|parallelogram|ସମାନ୍ତର ଚତୁର୍ଭୁଜ|समांतर चतुर्भुज|parallelogram shape geometry
08_Shapes|semicircle|ଅର୍ଦ୍ଧବୃତ୍ତ|अर्धवृत्त|semicircle shape geometry
08_Shapes|ring|ବଳୟ|छल्ला|ring annulus shape geometry
08_Shapes|diamond|ହୀରକ ଆକାର|हीरे का आकार|diamond shape geometry
08_Shapes|cuboid|ଆୟତଘନ|घनाभ|cuboid 3d shape
08_Shapes|heptagon|ସପ୍ତଭୁଜ|सप्तभुज|heptagon shape geometry
08_Shapes|decagon|ଦଶଭୁଜ|दशभुज|decagon shape geometry
08_Shapes|hemisphere|ଅର୍ଦ୍ଧଗୋଲକ|अर्धगोला|hemisphere 3d shape
08_Shapes|arrow|ତୀର|तीर|arrow shape
08_Shapes|cross|କ୍ରସ|क्रॉस|cross shape plus
08_Shapes|line|ସରଳ ରେଖା|रेखा|straight line geometry
08_Shapes|curve|ବକ୍ର ରେଖା|वक्र रेखा|curve line geometry
08_Shapes|spiral|ସର୍ପିଳ|सर्पिल|spiral shape
08_Shapes|kite|ଘୁଡ଼ି ଆକାର|पतंग आकार|kite quadrilateral shape geometry
09_Fruits|almond|ବାଦାମ|बादाम|
09_Fruits|apple|ସେଓ|सेब|apple fruit
09_Fruits|banana|କଦଳୀ|केला|
09_Fruits|betel nut|ଗୁଆ|सुपारी|betel nut areca
09_Fruits|blackberry|କଳା ବେରି|ब्लैकबेरी|
09_Fruits|cashew nut|କାଜୁ|काजू|
09_Fruits|cherry|ଚେରି|चेरी|
09_Fruits|coconut|ନଡ଼ିଆ|नारियल|
09_Fruits|custard apple|ସୀତାଫଳ|सीताफल|
09_Fruits|dried dates|ଛୁହାରା|छुहारा|
09_Fruits|flax seeds|ଅଳସି|अलसी|
09_Fruits|grapes|ଅଙ୍ଗୁର|अंगूर|
09_Fruits|groundnut|ଚିନାବାଦାମ|मूंगफली|peanut
09_Fruits|guava|ପିଜୁଳି|अमरूद|
09_Fruits|jackfruit|ପଣସ|कटहल|
09_Fruits|kiwi|କିୱି|कीवी|
09_Fruits|lemon|ଲେମ୍ବୁ|नींबू|
09_Fruits|litchi|ଲିଚି|लीची|lychee fruit
09_Fruits|mango|ଆମ୍ବ|आम|
09_Fruits|muskmelon|ଖରଭୁଜ|खरबूजा|
09_Fruits|orange|କମଳା|संतरा|
09_Fruits|papaya|ଅମୃତଭଣ୍ଡା|पपीता|
09_Fruits|pear|ନାସପାତି|नाशपाती|
09_Fruits|pineapple|ଅନାନାସ|अनानास|pineapple fruit
09_Fruits|pistachio|ପିସ୍ତା|पिस्ता|
09_Fruits|pomegranate|ଡାଳିମ୍ବ|अनार|
09_Fruits|raisin|କିସମିସ|किशमिश|
09_Fruits|sapodilla|ସପୋଟା|चीकू|sapodilla chikoo fruit
09_Fruits|sugarcane|ଆଖୁ|गन्ना|
09_Fruits|tamarind|ତେନ୍ତୁଳି|इमली|
09_Fruits|walnuts|ଆଖରୋଟ|अखरोट|walnut
09_Fruits|watermelon|ତରଭୁଜ|तरबूज|
09_Fruits|apricot|ଖୁବାନି|खुबानी|
09_Fruits|plum|ଆଳୁବୁଖରା|आलूबुखारा|
09_Fruits|peach|ପିଚ୍|आड़ू|
09_Fruits|strawberry|ଷ୍ଟ୍ରବେରି|स्ट्रॉबेरी|
09_Fruits|blueberry|ବ୍ଲୁବେରି|ब्लूबेरी|
09_Fruits|raspberry|ରାସବେରି|रास्पबेरी|
09_Fruits|mulberry|ତୁତ|शहतूत|
09_Fruits|gooseberry|ଅଁଳା|आंवला|amla indian gooseberry fruit
09_Fruits|black plum|ଜାମୁ|जामुन|jamun black plum fruit
09_Fruits|wood apple|କଇଥ|कैथ|wood apple fruit
09_Fruits|bael|ବେଲ|बेल|bael fruit
09_Fruits|star fruit|କର୍ମଙ୍ଗା|कमरख|star fruit carambola
09_Fruits|fig|ଡିମ୍ବିରି|अंजीर|
09_Fruits|dragon fruit|ଡ୍ରାଗନ ଫ୍ରୁଟ|ड्रैगन फ्रूट|
09_Fruits|avocado|ଆଭୋକାଡୋ|एवोकाडो|
09_Fruits|sweet lime|ମୋସମ୍ବି|मौसंबी|sweet lime mosambi fruit
09_Fruits|grapefruit|ଗ୍ରେପ୍‌ଫ୍ରୁଟ|चकोतरा|
09_Fruits|passion fruit|ପାସନ ଫ୍ରୁଟ|पैशन फ्रूट|
09_Fruits|cranberry|କ୍ରାନବେରି|क्रैनबेरी|
09_Fruits|jujube|ବରକୋଳି|बेर|jujube ber fruit
09_Fruits|dates|ଖଜୁରୀ|खजूर|dates fruit
09_Fruits|chestnut|ଚେଷ୍ଟନଟ୍|चेस्टनट|chestnut nut
09_Fruits|olive|ଜଳପାଇ|जैतून|olive fruit
09_Fruits|persimmon|ପର୍ସିମନ|पर्सिमन|
09_Fruits|nectarine|ନେକ୍ଟାରିନ|नेक्टराइन|
09_Fruits|tangerine|ଟାଞ୍ଜେରିନ|टैंजेरीन|
09_Fruits|honeydew melon|ହନିଡ୍ୟୁ ମେଲନ|हनीड्यू खरबूजा|
09_Fruits|fox nut|ମଖାନା|मखाना|makhana fox nut
09_Fruits|hazelnut|ହେଜେଲନଟ୍|हेज़लनट|
09_Fruits|palmyra fruit|ତାଳ|ताड़ का फल|palmyra palm fruit ice apple
09_Fruits|dry fruits|ଶୁଖିଲା ଫଳ|सूखे मेवे|mixed dry fruits
10_Vegetables|beans|ବିନ୍ସ|बीन्स|green beans vegetable
10_Vegetables|beetroot|ବିଟ|चुकंदर|
10_Vegetables|bitter gourd|କଲରା|करेला|
10_Vegetables|bottle gourd|ଲାଉ|लौकी|
10_Vegetables|brinjal|ବାଇଗଣ|बैंगन|
10_Vegetables|broccoli|ବ୍ରୋକୋଲି|ब्रोकली|
10_Vegetables|cabbage|ବନ୍ଧାକୋବି|पत्ता गोभी|
10_Vegetables|capsicum|କ୍ୟାପ୍ସିକମ|शिमला मिर्च|
10_Vegetables|carrot|ଗାଜର|गाजर|
10_Vegetables|cauliflower|ଫୁଲକୋବି|फूलगोभी|
10_Vegetables|chilly|ଲଙ୍କା|मिर्च|green chilli
10_Vegetables|coriander|ଧନିଆ|धनिया|
10_Vegetables|corn|ମକା|मक्का|
10_Vegetables|cucumber|କାକୁଡ଼ି|खीरा|
10_Vegetables|curry leaf|ଭୃଷଙ୍ଗ|करी पत्ता|
10_Vegetables|french beans|ଫ୍ରେଞ୍ଚ ବିନ୍ସ|फ्रेंच बीन्स|
10_Vegetables|garlic|ରସୁଣ|लहसुन|
10_Vegetables|ginger|ଅଦା|अदरक|
10_Vegetables|ladyfinger|ଭେଣ୍ଡି|भिंडी|okra ladyfinger vegetable
10_Vegetables|mushroom|ଛତୁ|मशरूम|
10_Vegetables|onion|ପିଆଜ|प्याज|
10_Vegetables|parwal|ପୋଟଳ|परवल|pointed gourd parwal vegetable
10_Vegetables|peas|ମଟର|मटर|green peas vegetable
10_Vegetables|potato|ଆଳୁ|आलू|
10_Vegetables|pumpkin seeds|କଖାରୁ ବିହନ|कद्दू के बीज|pumpkin seeds food
10_Vegetables|pumpkin|କଖାରୁ|कद्दू|
10_Vegetables|radish|ମୂଳା|मूली|
10_Vegetables|spinach|ପାଳଙ୍ଗ|पालक|
10_Vegetables|sweet potato|ରଙ୍ଗା ଆଳୁ|शकरकंद|
10_Vegetables|tomato|ଟମାଟୋ|टमाटर|
10_Vegetables|lettuce|ଲେଟୁସ|सलाद पत्ता|
10_Vegetables|celery|ସେଲେରି|अजमोदा|
10_Vegetables|turnip|ଶଳଗମ|शलजम|
10_Vegetables|yam|ଓଲ|जिमीकंद|elephant foot yam vegetable
10_Vegetables|taro|ସରୁ|अरबी|taro colocasia vegetable
10_Vegetables|ridge gourd|ଝୁଙ୍ଗା|तोरई|
10_Vegetables|snake gourd|ଚିଚିଣ୍ଡା|चिचिंडा|
10_Vegetables|drumstick|ସଜନା ଛୁଇଁ|सहजन की फली|drumstick moringa vegetable
10_Vegetables|raw banana|କଞ୍ଚା କଦଳୀ|कच्चा केला|
10_Vegetables|raw papaya|କଞ୍ଚା ଅମୃତଭଣ୍ଡା|कच्चा पपीता|
10_Vegetables|spring onion|ପିଆଜ କଲି|हरा प्याज|
10_Vegetables|mint|ପୋଦିନା|पुदीना|mint leaves
10_Vegetables|fenugreek|ମେଥି|मेथी|fenugreek leaves methi
10_Vegetables|mustard greens|ସୋରିଷ ଶାଗ|सरसों का साग|
10_Vegetables|cluster beans|ଗୁଆର|ग्वार फली|cluster beans guar
10_Vegetables|broad beans|ଶିମ୍ବ|सेम|broad beans
10_Vegetables|sweet corn|ମିଠା ମକା|स्वीट कॉर्न|
10_Vegetables|zucchini|ଜୁକିନି|ज़ुकीनी|
10_Vegetables|asparagus|ଆସ୍ପାରାଗସ|शतावरी|
10_Vegetables|turmeric|ହଳଦୀ|हल्दी|raw turmeric
10_Vegetables|ivy gourd|ତେଲକୁଚା|कुंदरू|ivy gourd tindora vegetable
10_Vegetables|banana flower|କଦଳୀ ଫୁଲ|केले का फूल|banana flower vegetable
10_Vegetables|soybean|ସୋୟାବିନ|सोयाबीन|
10_Vegetables|red cabbage|ଲାଲ ବନ୍ଧାକୋବି|लाल पत्ता गोभी|
10_Vegetables|kohlrabi|ଓଲକୋବି|गाँठ गोभी|
10_Vegetables|leafy greens|ଶାଗ|साग|leafy greens vegetable india
11_Flowers|butterfly pea|ଅପରାଜିତା|अपराजिता|butterfly pea flower
11_Flowers|champak|ଚମ୍ପା|चंपा|champak flower
11_Flowers|dahlia|ଡାହଲିଆ|डहलिया|
11_Flowers|datura|ଧତୁରା|धतूरा|datura flower
11_Flowers|garden daisy|ଡେଜି|डेजी|daisy flower
11_Flowers|gulmohar|କୃଷ୍ଣଚୂଡ଼ା|गुलमोहर|gulmohar flower
11_Flowers|jasmine|ମଲ୍ଲୀ|चमेली|
11_Flowers|lily|ଲିଲି|लिली|lily flower
11_Flowers|lotus|ପଦ୍ମ|कमल|lotus flower
11_Flowers|marigold|ଗେଣ୍ଡୁ|गेंदा|
11_Flowers|moonbeam|ଚନ୍ଦ୍ରକାନ୍ତି|चंद्रकांति|moonbeam flower
11_Flowers|rose|ଗୋଲାପ|गुलाब|
11_Flowers|saffron|କେସରୀ|केसरिया|saffron crocus flower
11_Flowers|sunflower|ସୂର୍ଯ୍ୟମୁଖୀ|सूरजमुखी|
11_Flowers|tuberose|ରଜନୀଗନ୍ଧା|रजनीगंधा|tuberose flower
11_Flowers|water lily|ଶାଳୁକ|कमलिनी|
11_Flowers|hibiscus|ମନ୍ଦାର|गुड़हल|
11_Flowers|tulip|ଟ୍ୟୁଲିପ|ट्यूलिप|
11_Flowers|orchid|ଅର୍କିଡ|ऑर्किड|
11_Flowers|lavender|ଲ୍ୟାଭେଣ୍ଡର|लैवेंडर|
11_Flowers|daffodil|ଡ୍ୟାଫୋଡିଲ|डैफोडिल|
11_Flowers|carnation|କାର୍ନେସନ|कार्नेशन|
11_Flowers|chrysanthemum|ଚନ୍ଦ୍ରମଲ୍ଲିକା|गुलदाउदी|
11_Flowers|pansy|ପ୍ୟାନସି|पैंज़ी|
11_Flowers|petunia|ପେଟୁନିଆ|पेटुनिया|
11_Flowers|zinnia|ଜିନିଆ|जिनिया|
11_Flowers|cosmos|କସମସ|कॉस्मोस|
11_Flowers|poppy|ପପି|पोस्त|
11_Flowers|bougainvillea|ବୋଗେନଭିଲା|बोगनवेलिया|
11_Flowers|oleander|କରବୀ|कनेर|
11_Flowers|night jasmine|ଶେଫାଳି|हरसिंगार|night jasmine parijat flower
11_Flowers|bakula|ବକୁଳ|मौलसिरी|bakula flower
11_Flowers|kadamba|କଦମ୍ବ|कदंब|kadamba flower
11_Flowers|kewda|କେତକୀ|केवड़ा|kewda flower
11_Flowers|peony|ପିଓନି|पियोनी|
11_Flowers|iris|ଆଇରିସ|आइरिस|
11_Flowers|gladiolus|ଗ୍ଲାଡିଓଲସ|ग्लैडियोलस|
11_Flowers|aster|ଆଷ୍ଟର|एस्टर|
11_Flowers|hydrangea|ହାଇଡ୍ରାଞ୍ଜିଆ|हाइड्रेंजिया|
11_Flowers|madhumalati|ମଧୁମାଳତୀ|मधुमालती|madhumalati rangoon creeper flower
11_Flowers|tagar|ଟଗର|टगर|tagar flower
11_Flowers|cherry blossom|ଚେରି ବ୍ଲସମ|चेरी ब्लॉसम|
11_Flowers|magnolia|ମ୍ୟାଗ୍ନୋଲିଆ|मैगनोलिया|
12_Animals|ant|ପିମ୍ପୁଡ଼ି|चींटी|ant insect
12_Animals|bear|ଭାଲୁ|भालू|
12_Animals|bee|ମହୁମାଛି|मधुमक्खी|honey bee insect
12_Animals|buffalo|ମଇଁଷି|भैंस|
12_Animals|bulbul|ବୁଲବୁଲ|बुलबुल|bulbul bird
12_Animals|bull|ଷଣ୍ଢ|बैल|
12_Animals|butterfly|ପ୍ରଜାପତି|तितली|
12_Animals|cat|ବିଲେଇ|बिल्ली|
12_Animals|cobra|ନାଗ|कोबरा|
12_Animals|rooster|ଗଞ୍ଜା|मुर्गा|rooster bird
12_Animals|cockroach|ଅସରପା|तिलचट्टा|
12_Animals|cow|ଗାଈ|गाय|
12_Animals|crab|କଙ୍କଡ଼ା|केकड़ा|
12_Animals|cuckoo|କୋଇଲି|कोयल|cuckoo bird
12_Animals|dog|କୁକୁର|कुत्ता|
12_Animals|dolphin|ଡଲଫିନ|डॉल्फिन|
12_Animals|duck|ବତକ|बत्तख|
12_Animals|eagle|ଛଞ୍ଚାଣ|बाज|
12_Animals|earthworm|କେଞ୍ଚୁଆ|केंचुआ|
12_Animals|eel|ବାମ|ईल|eel fish
12_Animals|elephant|ହାତୀ|हाथी|
12_Animals|fox|ଶିଆଳ|लोमड़ी|
12_Animals|frog|ବେଙ୍ଗ|मेंढक|
12_Animals|swan|ରାଜହଂସ|राजहंस|swan bird
12_Animals|house sparrow|ଚଟିଆ|गौरैया|house sparrow bird
12_Animals|giraffe|ଜିରାଫ|जिराफ|
12_Animals|goat|ଛେଳି|बकरी|
12_Animals|grasshopper|ଝିଙ୍କା|टिड्डा|
12_Animals|goose|ହଂସ|हंस|goose bird
12_Animals|hen|ମାଇକୁକୁଡ଼ା|मुर्गी|hen chicken
12_Animals|hippopotamus|ପାଣିହାତୀ|जलहस्ती|
12_Animals|horse|ଘୋଡ଼ା|घोड़ा|
12_Animals|jellyfish|ଜେଲିଫିଶ|जेलीफ़िश|
12_Animals|kangaroo|କାଙ୍ଗାରୁ|कंगारू|
12_Animals|crow|କାଉ|कौआ|crow bird
12_Animals|ladybug|ଲେଡିବଗ|लेडीबग|
12_Animals|lion|ସିଂହ|शेर|
12_Animals|lizard|ଝିଟିପିଟି|छिपकली|
12_Animals|lobster|ଲବଷ୍ଟର|लॉबस्टर|
12_Animals|kingfisher|ମାଛରଙ୍କା|मछरंगा|kingfisher bird
12_Animals|manatee|ମାନାଟି|मैनेटी|
12_Animals|peahen|ମୟୂରୀ|मयूरी|peahen bird
12_Animals|monkey|ମାଙ୍କଡ଼|बंदर|
12_Animals|mosquito|ମଶା|मच्छर|
12_Animals|octopus|ଅକ୍ଟୋପସ|ऑक्टोपस|
12_Animals|oyster|ଶାମୁକା|सीप|
12_Animals|peacock|ମୟୂର|मोर|
12_Animals|owl|ପେଚା|उल्लू|owl bird
12_Animals|penguin|ପେଙ୍ଗୁଇନ|पेंगुइन|
12_Animals|polar bear|ଧ୍ରୁବୀୟ ଭାଲୁ|ध्रुवीय भालू|
12_Animals|scorpion|ବିଛା|बिच्छू|
12_Animals|sea otter|ସମୁଦ୍ର ଓଟର|समुद्री ऊदबिलाव|
12_Animals|seahorse|ସମୁଦ୍ର ଘୋଡ଼ା|समुद्री घोड़ा|
12_Animals|seal|ସିଲ|सील|seal sea animal
12_Animals|shark|ଶାର୍କ|शार्क|
12_Animals|sheep|ମେଣ୍ଢା|भेड़|
12_Animals|snake|ସାପ|साँप|
12_Animals|spider|ମାକଡ଼ସା|मकड़ी|
12_Animals|squid|ସ୍କ୍ୱିଡ|स्क्विड|
12_Animals|starfish|ତାରାମାଛ|स्टारफ़िश|
12_Animals|termite|ଉଇ|दीमक|termite insect
12_Animals|tiger|ବାଘ|बाघ|
12_Animals|turtle|କଇଁଛ|कछुआ|
12_Animals|vulture|ଶାଗୁଣା|गिद्ध|
12_Animals|whale|ତିମି|व्हेल|
12_Animals|wolf|ଗଧିଆ|भेड़िया|
12_Animals|woodpecker|କାଠଠୋକା|कठफोड़वा|
12_Animals|zebra|ଜେବ୍ରା|ज़ेबरा|
12_Animals|rabbit|ଠେକୁଆ|खरगोश|
12_Animals|deer|ହରିଣ|हिरण|
12_Animals|camel|ଓଟ|ऊँट|
12_Animals|donkey|ଗଧ|गधा|
12_Animals|pig|ଘୁଷୁରି|सूअर|
12_Animals|rat|ମୂଷା|चूहा|
12_Animals|squirrel|କାଠବିରାଳି|गिलहरी|
12_Animals|bat|ବାଦୁଡ଼ି|चमगादड़|bat flying mammal animal
12_Animals|leopard|ଚିତାବାଘ|तेंदुआ|
12_Animals|cheetah|ଚିତା|चीता|
12_Animals|rhinoceros|ଗଣ୍ଡା|गैंडा|
12_Animals|panda|ପାଣ୍ଡା|पांडा|
12_Animals|koala|କୋଆଲା|कोआला|
12_Animals|gorilla|ଗୋରିଲା|गोरिल्ला|
12_Animals|chimpanzee|ଶିମ୍ପାଞ୍ଜି|चिंपैंज़ी|
12_Animals|crocodile|କୁମ୍ଭୀର|मगरमच्छ|
12_Animals|hyena|ହାଇନା|लकड़बग्घा|
12_Animals|mongoose|ନକୁଳ|नेवला|
12_Animals|porcupine|ଶଜାରୁ|साही|
12_Animals|bison|ବାଇସନ|बाइसन|
12_Animals|yak|ୟାକ|याक|
12_Animals|llama|ଲାମା|लामा|
12_Animals|parrot|ଶୁଆ|तोता|parrot bird
12_Animals|pigeon|ପାରା|कबूतर|pigeon bird
12_Animals|flamingo|ଫ୍ଲେମିଙ୍ଗୋ|फ्लेमिंगो|
12_Animals|pelican|ପେଲିକାନ|पेलिकन|
12_Animals|sarus crane|ସାରସ|सारस|sarus crane bird
12_Animals|heron|ବଗ|बगुला|heron bird
12_Animals|myna|ସାରିକା|मैना|myna bird
12_Animals|hornbill|ଧନେଶ|धनेश|hornbill bird
12_Animals|ostrich|ଅଷ୍ଟ୍ରିଚ|शुतुरमुर्ग|
12_Animals|turkey|ଟର୍କି|टर्की|turkey bird
12_Animals|fly|ମାଛି|मक्खी|housefly insect
12_Animals|dragonfly|ଫଡ଼ିଙ୍ଗ|ड्रैगनफ्लाई|dragonfly insect
12_Animals|caterpillar|ଶୁଆପୋକ|इल्ली|caterpillar insect
12_Animals|snail|ଶମ୍ବୁକ|घोंघा|snail animal
12_Animals|centipede|ଶତପଦୀ|कनखजूरा|centipede insect
12_Animals|moth|ପତଙ୍ଗ|पतंगा|moth insect
12_Animals|chameleon|କୃକଲାସ|गिरगिट|
12_Animals|python|ଅଜଗର|अजगर|python snake
12_Animals|monitor lizard|ଗୋଧି|गोह|monitor lizard animal
12_Animals|fish|ମାଛ|मछली|fish swimming
12_Animals|goldfish|ସୁନା ମାଛ|सुनहरी मछली|
12_Animals|shrimp|ଚିଙ୍ଗୁଡ଼ି|झींगा|shrimp prawn
12_Animals|rohu fish|ରୁହି ମାଛ|रोहू मछली|rohu fish
12_Animals|hilsa|ଇଲିଶି|हिलसा|hilsa fish
12_Animals|olive ridley turtle|ଅଲିଭ ରିଡ଼ଲି କଇଁଛ|ऑलिव रिडले कछुआ|olive ridley sea turtle
12_Animals|irrawaddy dolphin|ଇରାବତୀ ଡଲଫିନ|इरावदी डॉल्फ़िन|irrawaddy dolphin
12_Animals|calf|ବାଛୁରୀ|बछड़ा|calf baby cow
12_Animals|puppy|କୁକୁର ଛୁଆ|पिल्ला|puppy dog
12_Animals|kitten|ବିଲେଇ ଛୁଆ|बिल्ली का बच्चा|kitten cat
12_Animals|lamb|ମେଣ୍ଢା ଛୁଆ|मेमना|lamb baby sheep
12_Animals|wild boar|ବଣୁଆ ଘୁଷୁରି|जंगली सूअर|wild boar
12_Animals|langur|ହନୁମାନ ବାନର|लंगूर|langur monkey
12_Animals|spotted deer|ଚିତଲ ହରିଣ|चीतल|spotted deer chital
12_Animals|walrus|ୱାଲରସ|वालरस|
12_Animals|orca|ଓର୍କା|ऑर्का|orca killer whale
12_Animals|stingray|ଷ୍ଟିଙ୍ଗରେ|स्टिंग रे|stingray fish
12_Animals|clownfish|କ୍ଲାଉନଫିସ|क्लाउन फिश|clownfish
12_Animals|sea lion|ସି ଲାୟନ|सी लायन|sea lion
13_Body_Parts|arm|ବାହୁ|बाँह|
13_Body_Parts|ear|କାନ|कान|
13_Body_Parts|elbow|କୁହୁଣୀ|कोहनी|
13_Body_Parts|eye|ଆଖି|आँख|
13_Body_Parts|eyebrow|ଆଖିଭୁଁଇଁ|भौंह|
13_Body_Parts|face|ମୁହଁ|चेहरा|
13_Body_Parts|fingers|ଆଙ୍ଗୁଠି|उंगलियाँ|
13_Body_Parts|foot|ପାଦ|पैर|
13_Body_Parts|hand|ହାତ|हाथ|
13_Body_Parts|head|ମୁଣ୍ଡ|सिर|
13_Body_Parts|knee|ଆଣ୍ଠୁ|घुटना|
13_Body_Parts|leg|ଗୋଡ଼|टाँग|
13_Body_Parts|lip|ଓଠ|होंठ|
13_Body_Parts|mouth|ପାଟି|मुँह|
13_Body_Parts|neck|ବେକ|गर्दन|
13_Body_Parts|nose|ନାକ|नाक|
13_Body_Parts|teeth|ଦାନ୍ତ|दाँत|
13_Body_Parts|toes|ପାଦ ଆଙ୍ଗୁଠି|पैर की उंगलियाँ|human toes foot body part
13_Body_Parts|hair|କେଶ|बाल|
13_Body_Parts|forehead|କପାଳ|माथा|
13_Body_Parts|cheek|ଗାଲ|गाल|
13_Body_Parts|chin|ଚିବୁକ|ठोड़ी|
13_Body_Parts|tongue|ଜିଭ|जीभ|
13_Body_Parts|throat|ଗଳା|गला|
13_Body_Parts|shoulder|କାନ୍ଧ|कंधा|
13_Body_Parts|chest|ଛାତି|छाती|
13_Body_Parts|back|ପିଠି|पीठ|human back body
13_Body_Parts|stomach|ପେଟ|पेट|
13_Body_Parts|waist|କଟି|कमर|
13_Body_Parts|thumb|ବୁଢ଼ା ଆଙ୍ଗୁଠି|अंगूठा|
13_Body_Parts|finger|ଆଙ୍ଗୁଠି|उंगली|
13_Body_Parts|palm|ତଳହାତ|हथेली|
13_Body_Parts|nail|ନଖ|नाखून|fingernail human body part
13_Body_Parts|wrist|ମଣିବନ୍ଧ|कलाई|
13_Body_Parts|ankle|ଗୁଲ୍ଫ|टखना|
13_Body_Parts|heel|ଗୋଇଠି|एड़ी|
13_Body_Parts|thigh|ଜଙ୍ଘ|जाँघ|
13_Body_Parts|skin|ଚର୍ମ|त्वचा|
13_Body_Parts|heart|ହୃଦୟ|हृदय|human heart organ
13_Body_Parts|brain|ମସ୍ତିଷ୍କ|दिमाग|human brain organ
13_Body_Parts|lungs|ଫୁସଫୁସ|फेफड़े|human lungs organ
13_Body_Parts|bone|ହାଡ଼|हड्डी|human bone
13_Body_Parts|muscle|ମାଂସପେଶୀ|मांसपेशी|human muscle
13_Body_Parts|blood|ରକ୍ତ|खून|blood drop
13_Body_Parts|beard|ଦାଢ଼ି|दाढ़ी|
13_Body_Parts|moustache|ଗୁମ୍ଫ|मूँछ|
13_Body_Parts|liver|ଯକୃତ|जिगर|human liver organ
13_Body_Parts|kidney|ବୃକ୍କ|गुर्दा|human kidney organ
13_Body_Parts|ribs|ପଞ୍ଜରା|पसलियाँ|human ribs
13_Body_Parts|navel|ନାଭି|नाभि|
13_Body_Parts|jaw|ହନୁ|जबड़ा|
13_Body_Parts|eyelid|ଆଖିପତା|पलक|
13_Body_Parts|nostril|ନାକ ଛିଦ୍ର|नथुना|
13_Body_Parts|fist|ମୁଠା|मुट्ठी|
13_Body_Parts|armpit|କାଖ|बगल|
13_Body_Parts|spine|ମେରୁଦଣ୍ଡ|रीढ़ की हड्डी|human spine
14_Emotions|angry|ରାଗ|गुस्सा|
14_Emotions|cry|କାନ୍ଦିବା|रोना|
14_Emotions|excited|ଉତ୍ସାହିତ|उत्साहित|
14_Emotions|happy|ଖୁସି|खुश|
14_Emotions|proud|ଗର୍ବିତ|गर्वित|
14_Emotions|sad|ଦୁଃଖୀ|उदास|
14_Emotions|scared|ଡରିବା|डरा हुआ|
14_Emotions|shy|ଲାଜ|शर्मीला|
14_Emotions|sleepy|ନିଦ୍ରାଳୁ|नींद आना|
14_Emotions|surprised|ଆଶ୍ଚର୍ଯ୍ୟ|आश्चर्यचकित|
14_Emotions|love|ପ୍ରେମ|प्यार|
14_Emotions|laughing|ହସିବା|हँसना|
14_Emotions|smiling|ମୁରୁକି ହସ|मुस्कुराना|
14_Emotions|worried|ଚିନ୍ତିତ|चिंतित|
14_Emotions|tired|କ୍ଳାନ୍ତ|थका हुआ|
14_Emotions|hungry|ଭୋକିଲା|भूखा|
14_Emotions|thirsty|ଶୋଷିଲା|प्यासा|
14_Emotions|bored|ବିରକ୍ତ|ऊबा हुआ|
14_Emotions|confused|ଦ୍ୱନ୍ଦ୍ୱରେ|उलझन में|
14_Emotions|lonely|ଏକୁଟିଆ|अकेला|
14_Emotions|jealous|ଈର୍ଷାଳୁ|ईर्ष्यालु|
14_Emotions|nervous|ଘାବରା|घबराया हुआ|
14_Emotions|brave|ସାହସୀ|बहादुर|
14_Emotions|kind|ଦୟାଳୁ|दयालु|
14_Emotions|calm|ଶାନ୍ତ|शांत|
14_Emotions|sick|ଅସୁସ୍ଥ|बीमार|
14_Emotions|ashamed|ଲଜ୍ଜିତ|शर्मिंदा|
14_Emotions|disgusted|ଘୃଣା|घृणा|
14_Emotions|grateful|କୃତଜ୍ଞ|आभारी|
14_Emotions|curious|କୌତୂହଳୀ|जिज्ञासु|
14_Emotions|hopeful|ଆଶାବାଦୀ|आशावान|
14_Emotions|cheerful|ଉଲ୍ଲସିତ|प्रसन्न|
14_Emotions|silly|ମଜାଳିଆ|मज़ाकिया|
14_Emotions|sleeping|ଶୋଇବା|सोना|
14_Emotions|determined|ଦୃଢ଼ ସଂକଳ୍ପ|दृढ़ निश्चयी|
15_Household|air conditioner|ଏସି|एयर कंडीशनर|
15_Household|bed|ଶଯ୍ୟା|बिस्तर|
15_Household|blender|ବ୍ଲେଣ୍ଡର|ब्लेंडर|
15_Household|ceiling fan|ଛାତ ପଙ୍ଖା|सीलिंग फैन|
15_Household|pressure cooker|କୁକର|प्रेशर कुकर|pressure cooker kitchen
15_Household|dishwasher|ଡିସୱାସର|डिशवॉशर|
15_Household|dustbin|ଆବର୍ଜନା ଡବା|कूड़ादान|dustbin trash can
15_Household|gas stove|ଗ୍ୟାସ ଚୁଲା|गैस चूल्हा|
15_Household|iron|ଇସ୍ତିରି|इस्तरी|clothes iron electric
15_Household|oven|ଓଭେନ|ओवन|
15_Household|refrigerator|ଫ୍ରିଜ|फ्रिज|
15_Household|sewing machine|ସିଲେଇ ମେସିନ|सिलाई मशीन|
15_Household|television|ଟେଲିଭିଜନ|टेलीविजन|
15_Household|toaster|ଟୋଷ୍ଟର|टोस्टर|
15_Household|vacuum cleaner|ଭ୍ୟାକ୍ୟୁମ କ୍ଲିନର|वैक्यूम क्लीनर|
15_Household|washing machine|ଧୋଇବା ମେସିନ|वाशिंग मशीन|
15_Household|water purifier|ପାଣି ଫିଲ୍ଟର|वॉटर प्यूरीफायर|
15_Household|water heater|ପାଣି ଗରମ କରିବା|वॉटर हीटर|
15_Household|table|ଟେବୁଲ|मेज़|
15_Household|chair|ଚଉକି|कुर्सी|
15_Household|sofa|ସୋଫା|सोफ़ा|
15_Household|almirah|ଆଲମିରା|अलमारी|
15_Household|mirror|ଦର୍ପଣ|आईना|
15_Household|wall clock|କାନ୍ଥ ଘଡ଼ି|दीवार घड़ी|
15_Household|light bulb|ବଲ୍ବ|बल्ब|
15_Household|door|ଦ୍ୱାର|दरवाज़ा|
15_Household|window|ଝରକା|खिड़की|
15_Household|broom|ଝାଡ଼ୁ|झाड़ू|
15_Household|bucket|ବାଲଟି|बाल्टी|
15_Household|mug|ମଗ|मग|
15_Household|plate|ଥାଳି|थाली|
15_Household|spoon|ଚାମଚ|चम्मच|
15_Household|glass|ଗ୍ଲାସ|गिलास|drinking glass household
15_Household|cup|କପ|कप|
15_Household|bowl|ବାଟି|कटोरी|
15_Household|knife|ଛୁରୀ|चाकू|kitchen knife
15_Household|fork|କଣ୍ଟା|काँटा|dinner fork
15_Household|pot|ହାଣ୍ଡି|हाँडी|cooking pot kitchen
15_Household|frying pan|କଡ଼ାଇ|कड़ाही|
15_Household|kettle|କେଟଲି|केतली|
15_Household|pillow|ବାଲିସ|तकिया|
15_Household|blanket|କମ୍ବଳ|कंबल|
15_Household|mat|ମାଦୁର|चटाई|
15_Household|curtain|ପରଦା|पर्दा|
15_Household|telephone|ଟେଲିଫୋନ|टेलीफोन|
15_Household|mobile phone|ମୋବାଇଲ|मोबाइल|
15_Household|torch|ଟର୍ଚ୍ଚ|टॉर्च|torch flashlight
15_Household|umbrella|ଛତା|छाता|
15_Household|lock|ତାଲା|ताला|padlock
15_Household|key|ଚାବି|चाबी|door key
15_Household|soap|ସାବୁନ|साबुन|
15_Household|towel|ତଉଲିଆ|तौलिया|
15_Household|comb|କଂଘେଇ|कंघी|
15_Household|toothbrush|ଦାନ୍ତ ବ୍ରଶ|टूथब्रश|
15_Household|scissors|କଞ୍ଚି|कैंची|
15_Household|hammer|ହାତୁଡ଼ି|हथौड़ा|
15_Household|ladder|ସିଢ଼ି|सीढ़ी|
15_Household|tap|ନଳ|नल|water tap
15_Household|table fan|ଟେବୁଲ ପଙ୍ଖା|टेबल फैन|
15_Household|lantern|ଲଣ୍ଠନ|लालटेन|
15_Household|candle|ମହମବତୀ|मोमबत्ती|
15_Household|matchbox|ଦିଆସିଲି|माचिस|
15_Household|mixer grinder|ମିକ୍ସର|मिक्सर ग्राइंडर|
15_Household|grinding stone|ଶିଲପୁଆ|सिलबट्टा|grinding stone sil batta
15_Household|bookshelf|ବହି ଆଲମାରୀ|किताबों की अलमारी|
15_Household|hanger|ହ୍ୟାଙ୍ଗର|हैंगर|clothes hanger
15_Household|inverter|ଇନଭର୍ଟର|इन्वर्टर|home inverter
15_Household|switch board|ସ୍ୱିଚ ବୋର୍ଡ|स्विच बोर्ड|electric switch board
15_Household|cot|ଖଟ|खाट|cot bed
15_Household|stool|ଷ୍ଟୁଲ|स्टूल|stool seat
15_Household|diya lamp|ଦୀପ|दीया|diya oil lamp
15_Household|photo frame|ଫଟୋ ଫ୍ରେମ|फोटो फ्रेम|
15_Household|flower vase|ଫୁଲଦାନୀ|फूलदान|
15_Household|dining table|ଖାଇବା ଟେବୁଲ|खाने की मेज़|
16_Transport|aeroplane|ବିମାନ|हवाई जहाज|aeroplane airplane flying
16_Transport|ambulance|ଆମ୍ବୁଲାନ୍ସ|एम्बुलेंस|
16_Transport|auto rickshaw|ଅଟୋ|ऑटो रिक्शा|auto rickshaw india
16_Transport|bicycle|ସାଇକେଲ|साइकिल|
16_Transport|bullock cart|ବଳଦ ଗାଡ଼ି|बैलगाड़ी|bullock cart india
16_Transport|bus|ବସ|बस|
16_Transport|car|କାର|कार|
16_Transport|fighter plane|ଯୁଦ୍ଧ ବିମାନ|लड़ाकू विमान|fighter jet
16_Transport|helicopter|ହେଲିକପ୍ଟର|हेलीकॉप्टर|
16_Transport|JCB|ଜେସିବି|जेसीबी|JCB excavator
16_Transport|jeep|ଜିପ|जीप|
16_Transport|rocket|ରକେଟ|रॉकेट|
16_Transport|scooter|ସ୍କୁଟର|स्कूटर|
16_Transport|ship|ଜାହାଜ|जहाज|
16_Transport|space shuttle|ସ୍ପେସ ସଟଲ|स्पेस शटल|
16_Transport|submarine|ଜଳଯାନ|पनडुब्बी|
16_Transport|tank|ଟ୍ୟାଙ୍କ|टैंक|army battle tank
16_Transport|tractor|ଟ୍ରାକ୍ଟର|ट्रैक्टर|
16_Transport|train|ଟ୍ରେନ|रेलगाड़ी|
16_Transport|truck|ଟ୍ରକ|ट्रक|
16_Transport|water scooter|ୱାଟର ସ୍କୁଟର|वॉटर स्कूटर|jet ski water scooter
16_Transport|motorcycle|ମୋଟରସାଇକେଲ|मोटरसाइकिल|
16_Transport|cycle rickshaw|ସାଇକେଲ ରିକ୍ସା|साइकिल रिक्शा|
16_Transport|taxi|ଟ୍ୟାକ୍ସି|टैक्सी|
16_Transport|van|ଭ୍ୟାନ|वैन|
16_Transport|metro train|ମେଟ୍ରୋ ଟ୍ରେନ|मेट्रो ट्रेन|
16_Transport|boat|ଡଙ୍ଗା|नाव|
16_Transport|cruise ship|କ୍ରୁଜ ଜାହାଜ|क्रूज़ जहाज़|
16_Transport|tram|ଟ୍ରାମ|ट्राम|
16_Transport|fire engine|ଅଗ୍ନିଶମ ଗାଡ଼ି|दमकल गाड़ी|
16_Transport|police car|ପୋଲିସ ଗାଡ଼ି|पुलिस की गाड़ी|
16_Transport|school bus|ସ୍କୁଲ ବସ|स्कूल बस|
16_Transport|horse cart|ଘୋଡ଼ା ଗାଡ଼ି|तांगा|horse cart tanga india
16_Transport|hot air balloon|ଗରମ ବାୟୁ ବେଲୁନ|गर्म हवा का गुब्बारा|
16_Transport|cable car|କେବୁଲ କାର|केबल कार|
16_Transport|bullet train|ବୁଲେଟ ଟ୍ରେନ|बुलेट ट्रेन|
16_Transport|crane|କ୍ରେନ|क्रेन|construction crane vehicle
16_Transport|bulldozer|ବୁଲଡୋଜର|बुलडोज़र|
16_Transport|road roller|ରୋଡ ରୋଲର|रोड रोलर|
16_Transport|dump truck|ଡମ୍ପର ଟ୍ରକ|डंपर ट्रक|
16_Transport|ferry|ଫେରି|फेरी|ferry boat
16_Transport|speed boat|ସ୍ପିଡବୋଟ|स्पीडबोट|
16_Transport|sailing boat|ପାଲ ଡଙ୍ଗା|पाल वाली नाव|sailing boat
16_Transport|jet plane|ଜେଟ ବିମାନ|जेट विमान|passenger jet plane
16_Transport|wheelchair|ହ୍ୱିଲଚେୟାର|व्हीलचेयर|
16_Transport|handcart|ଠେଲା ଗାଡ଼ି|ठेला|handcart india
16_Transport|tanker truck|ଟ୍ୟାଙ୍କର|टैंकर|tanker truck
16_Transport|electric car|ଇଲେକ୍ଟ୍ରିକ କାର|इलेक्ट्रिक कार|electric car charging
16_Transport|e-rickshaw|ଇ-ରିକ୍ସା|ई-रिक्शा|e rickshaw india
16_Transport|steam engine|ବାଷ୍ପ ଇଞ୍ଜିନ|भाप इंजन|steam engine train
16_Transport|tempo|ଟେମ୍ପୋ|टेम्पो|tempo vehicle india
16_Transport|kayak|କାୟାକ|कयाक|kayak boat
16_Transport|lifeboat|ଜୀବନ ରକ୍ଷା ଡଙ୍ଗା|लाइफबोट|lifeboat
17_Professions|barber|ନାଇ|नाई|
17_Professions|builder|ନିର୍ମାତା|बिल्डर|construction worker builder
17_Professions|doctor|ଡାକ୍ତର|डॉक्टर|
17_Professions|electrician|ବିଦ୍ୟୁତ କାରିଗର|इलेक्ट्रीशियन|
17_Professions|farmer|ଚାଷୀ|किसान|
17_Professions|magician|ଯାଦୁଗର|जादूगर|
17_Professions|nurse|ନର୍ସ|नर्स|
17_Professions|painter|ଚିତ୍ରକର|पेंटर|house wall painter
17_Professions|photographer|ଫଟୋଗ୍ରାଫର|फोटोग्राफर|
17_Professions|pilot|ପାଇଲଟ|पायलट|
17_Professions|police|ପୋଲିସ|पुलिस|police officer
17_Professions|postman|ଡାକିଆ|पोस्टमैन|
17_Professions|potter|କୁମ୍ଭାର|कुम्हार|potter making clay pot
17_Professions|scientist|ବୈଜ୍ଞାନିକ|वैज्ञानिक|scientist laboratory
17_Professions|singer|ଗାୟକ|गायक|
17_Professions|soldier|ସୈନିକ|सैनिक|
17_Professions|tailor|ଦରଜି|दर्जी|
17_Professions|teacher|ଶିକ୍ଷକ|शिक्षक|
17_Professions|waiter|ୱେଟର|वेटर|
17_Professions|engineer|ଇଞ୍ଜିନିୟର|इंजीनियर|
17_Professions|lawyer|ଓକିଲ|वकील|
17_Professions|judge|ବିଚାରପତି|न्यायाधीश|
17_Professions|driver|ଡ୍ରାଇଭର|ड्राइवर|driver car profession
17_Professions|cook|ରୋଷେୟା|रसोइया|cook chef kitchen
17_Professions|baker|ବେକର|बेकर|baker bakery profession
17_Professions|fisherman|ମାଛୁଆ|मछुआरा|
17_Professions|carpenter|ବଢ଼େଇ|बढ़ई|
17_Professions|blacksmith|କମାର|लोहार|
17_Professions|goldsmith|ସୁନାର|सुनार|goldsmith jeweller
17_Professions|mason|ରାଜମିସ୍ତ୍ରୀ|राजमिस्त्री|mason bricklayer
17_Professions|plumber|ପ୍ଲମ୍ବର|प्लंबर|
17_Professions|mechanic|ମେକାନିକ|मैकेनिक|
17_Professions|shopkeeper|ଦୋକାନୀ|दुकानदार|
17_Professions|vegetable seller|ପରିବା ବିକ୍ରେତା|सब्ज़ीवाला|vegetable seller india
17_Professions|milkman|ଦୁଧ ବିକ୍ରେତା|दूधवाला|milkman india
17_Professions|cobbler|ମୋଚି|मोची|cobbler shoe repair
17_Professions|weaver|ତନ୍ତୀ|बुनकर|weaver handloom
17_Professions|washerman|ଧୋବା|धोबी|washerman dhobi india
17_Professions|gardener|ମାଳୀ|माली|
17_Professions|firefighter|ଅଗ୍ନିଶମ କର୍ମୀ|दमकलकर्मी|
17_Professions|astronaut|ମହାକାଶଚାରୀ|अंतरिक्ष यात्री|
17_Professions|dentist|ଦନ୍ତ ଚିକିତ୍ସକ|दंत चिकित्सक|
17_Professions|veterinarian|ପଶୁ ଚିକିତ୍ସକ|पशु चिकित्सक|
17_Professions|journalist|ସାମ୍ବାଦିକ|पत्रकार|
17_Professions|artist|କଳାକାର|कलाकार|
17_Professions|dancer|ନର୍ତ୍ତକ|नर्तक|
17_Professions|musician|ସଙ୍ଗୀତଜ୍ଞ|संगीतकार|
17_Professions|actor|ଅଭିନେତା|अभिनेता|
17_Professions|sportsman|ଖେଳାଳି|खिलाड़ी|sportsman athlete
17_Professions|bank clerk|ବ୍ୟାଙ୍କ କର୍ମଚାରୀ|बैंक कर्मचारी|
17_Professions|security guard|ପ୍ରହରୀ|चौकीदार|
17_Professions|shepherd|ମେଷପାଳକ|चरवाहा|
17_Professions|priest|ପୂଜାରୀ|पुजारी|priest pandit india
17_Professions|professor|ପ୍ରାଧ୍ୟାପକ|प्रोफेसर|
17_Professions|pharmacist|ଔଷଧ ବିକ୍ରେତା|दवा विक्रेता|pharmacist medical shop
17_Professions|architect|ସ୍ଥପତି|वास्तुकार|
17_Professions|writer|ଲେଖକ|लेखक|writer author
17_Professions|bus conductor|କଣ୍ଡକ୍ଟର|कंडक्टर|bus conductor
17_Professions|chef|ଶେଫ|शेफ|
17_Professions|cleaner|ସଫେଇ କର୍ମୀ|सफाईकर्मी|street cleaner sweeper
17_Professions|coach|ପ୍ରଶିକ୍ଷକ|प्रशिक्षक|sports coach
17_Professions|cameraman|କ୍ୟାମେରାମ୍ୟାନ|कैमरामैन|
17_Professions|tea seller|ଚା ବିକ୍ରେତା|चायवाला|tea seller chaiwala india
17_Professions|ice cream seller|ଆଇସକ୍ରିମ ବିକ୍ରେତା|आइसक्रीम वाला|
25_Computers|CPU|ସିପିୟୁ|सीपीयू|computer cpu cabinet
25_Computers|headphone|ହେଡଫୋନ|हेडफोन|
25_Computers|keyboard|କିବୋର୍ଡ|कीबोर्ड|
25_Computers|monitor|ମନିଟର|मॉनिटर|
25_Computers|mouse|ମାଉସ|माउस|computer mouse
25_Computers|pen drive|ପେନ ଡ୍ରାଇଭ|पेन ड्राइव|usb pen drive
25_Computers|printer|ପ୍ରିଣ୍ଟର|प्रिंटर|
25_Computers|scanner|ସ୍କାନର|स्कैनर|
25_Computers|speakers|ସ୍ପିକର|स्पीकर|computer speakers
25_Computers|UPS|ୟୁପିଏସ|यूपीएस|UPS uninterruptible power supply for computer
25_Computers|web camera|ୱେବ କ୍ୟାମେରା|वेब कैमरा|webcam
25_Computers|laptop|ଲାପଟପ|लैपटॉप|
25_Computers|desktop computer|ଡେସ୍କଟପ କମ୍ପ୍ୟୁଟର|डेस्कटॉप कंप्यूटर|
25_Computers|tablet|ଟାବଲେଟ|टैबलेट|tablet computer
25_Computers|smartphone|ସ୍ମାର୍ଟଫୋନ|स्मार्टफोन|
25_Computers|microphone|ମାଇକ୍ରୋଫୋନ|माइक्रोफोन|
25_Computers|router|ରାଉଟର|राउटर|wifi router
25_Computers|modem|ମଡେମ|मॉडेम|internet modem
25_Computers|hard disk|ହାର୍ଡ ଡିସ୍କ|हार्ड डिस्क|computer hard disk
25_Computers|CD|ସିଡି|सीडी|compact disc cd
25_Computers|memory card|ମେମୋରୀ କାର୍ଡ|मेमोरी कार्ड|sd memory card
25_Computers|projector|ପ୍ରୋଜେକ୍ଟର|प्रोजेक्टर|
25_Computers|joystick|ଜୟଷ୍ଟିକ|जॉयस्टिक|joystick game
25_Computers|mouse pad|ମାଉସ ପ୍ୟାଡ|माउस पैड|
25_Computers|USB cable|ୟୁଏସବି କେବୁଲ|यूएसबी केबल|usb cable
25_Computers|charger|ଚାର୍ଜର|चार्जर|mobile charger
25_Computers|power bank|ପାୱାର ବ୍ୟାଙ୍କ|पावर बैंक|
25_Computers|motherboard|ମଦରବୋର୍ଡ|मदरबोर्ड|computer motherboard
25_Computers|RAM|ରାମ|रैम|RAM memory module computer
25_Computers|smart watch|ସ୍ମାର୍ଟ ୱାଚ|स्मार्ट वॉच|
25_Computers|game controller|ଗେମ କଣ୍ଟ୍ରୋଲର|गेम कंट्रोलर|game controller gamepad
25_Computers|WiFi|ୱାଇ-ଫାଇ|वाई-फाई|wifi symbol
25_Computers|robot|ରୋବଟ|रोबोट|robot toy
25_Computers|drone|ଡ୍ରୋନ|ड्रोन|drone camera
26_Festivals|Buddha Purnima|ବୁଦ୍ଧ ପୂର୍ଣ୍ଣିମା|बुद्ध पूर्णिमा|Buddha Purnima festival
26_Festivals|Dasahera|ଦଶହରା|दशहरा|Dussehra festival
26_Festivals|Diwali|ଦୀପାବଳି|दिवाली|Diwali festival
26_Festivals|Eid|ଈଦ|ईद|Eid festival
26_Festivals|Holi|ହୋଲି|होली|Holi festival colors
26_Festivals|Independence Day|ସ୍ୱାଧୀନତା ଦିବସ|स्वतंत्रता दिवस|India Independence Day
26_Festivals|Janmashtami|ଜନ୍ମାଷ୍ଟମୀ|जन्माष्टमी|Janmashtami festival
26_Festivals|Kartika Purnima|କାର୍ତ୍ତିକ ପୂର୍ଣ୍ଣିମା|कार्तिक पूर्णिमा|Kartika Purnima Boita Bandana Cuttack
26_Festivals|Kumara Purnima|କୁମାର ପୂର୍ଣ୍ଣିମା|कुमार पूर्णिमा|Kumar Purnima Odisha festival
26_Festivals|Nuakhai|ନୂଆଖାଇ|नुआखाई|Nuakhai festival Odisha
26_Festivals|Raksha Bandhan|ରକ୍ଷାବନ୍ଧନ|रक्षाबंधन|Raksha Bandhan festival rakhi
26_Festivals|Rath Yatra|ରଥଯାତ୍ରା|रथ यात्रा|Rath Yatra Puri Jagannath
26_Festivals|Republic Day|ଗଣତନ୍ତ୍ର ଦିବସ|गणतंत्र दिवस|India Republic Day parade
26_Festivals|Shivaratri|ଶିବରାତ୍ରି|शिवरात्रि|Maha Shivaratri
26_Festivals|Christmas|କ୍ରିସମସ|क्रिसमस|Christmas festival
26_Festivals|Durga Puja|ଦୁର୍ଗା ପୂଜା|दुर्गा पूजा|Durga Puja festival
26_Festivals|Kali Puja|କାଳୀ ପୂଜା|काली पूजा|Kali Puja festival
26_Festivals|Ganesh Chaturthi|ଗଣେଶ ଚତୁର୍ଥୀ|गणेश चतुर्थी|Ganesh Chaturthi festival
26_Festivals|Saraswati Puja|ସରସ୍ୱତୀ ପୂଜା|सरस्वती पूजा|Saraswati Puja festival
26_Festivals|Laxmi Puja|ଲକ୍ଷ୍ମୀ ପୂଜା|लक्ष्मी पूजा|Laxmi Puja festival
26_Festivals|Makar Sankranti|ମକର ସଂକ୍ରାନ୍ତି|मकर संक्रांति|Makar Sankranti kite festival
26_Festivals|Pongal|ପୋଙ୍ଗଲ|पोंगल|Pongal festival
26_Festivals|Onam|ଓଣମ|ओणम|Onam festival Kerala
26_Festivals|Navratri|ନବରାତ୍ରି|नवरात्रि|Navratri festival garba
26_Festivals|Ram Navami|ରାମ ନବମୀ|राम नवमी|Ram Navami festival
26_Festivals|Hanuman Jayanti|ହନୁମାନ ଜୟନ୍ତୀ|हनुमान जयंती|Hanuman Jayanti festival
26_Festivals|Baisakhi|ବୈଶାଖୀ|बैसाखी|Baisakhi festival
26_Festivals|Lohri|ଲୋହରି|लोहड़ी|Lohri festival bonfire
26_Festivals|Gandhi Jayanti|ଗାନ୍ଧୀ ଜୟନ୍ତୀ|गांधी जयंती|Gandhi Jayanti
26_Festivals|Teachers Day|ଶିକ୍ଷକ ଦିବସ|शिक्षक दिवस|Teachers Day India
26_Festivals|Childrens Day|ଶିଶୁ ଦିବସ|बाल दिवस|Childrens Day India
26_Festivals|New Year|ନୂଆ ବର୍ଷ|नया साल|New Year celebration fireworks
26_Festivals|Good Friday|ଗୁଡ ଫ୍ରାଇଡେ|गुड फ्राइडे|Good Friday
26_Festivals|Easter|ଇଷ୍ଟର|ईस्टर|Easter festival eggs
26_Festivals|Mahavir Jayanti|ମହାବୀର ଜୟନ୍ତୀ|महावीर जयंती|Mahavir Jayanti
26_Festivals|Guru Nanak Jayanti|ଗୁରୁନାନକ ଜୟନ୍ତୀ|गुरु नानक जयंती|Guru Nanak Jayanti
26_Festivals|Chhath Puja|ଛଠ ପୂଜା|छठ पूजा|Chhath Puja festival
26_Festivals|Bali Yatra|ବାଲି ଯାତ୍ରା|बाली यात्रा|Bali Yatra Cuttack festival
26_Festivals|Raja Parba|ରଜ ପର୍ବ|रज पर्व|Raja Parba Odisha festival swing
26_Festivals|Chandan Yatra|ଚନ୍ଦନ ଯାତ୍ରା|चंदन यात्रा|Chandan Yatra Puri festival
26_Festivals|Dola Purnima|ଦୋଳ ପୂର୍ଣ୍ଣିମା|दोल पूर्णिमा|Dola Purnima Odisha festival
26_Festivals|Akshaya Tritiya|ଅକ୍ଷୟ ତୃତୀୟା|अक्षय तृतीया|Akshaya Tritiya
27_Currency|One rupee coin|ଏକ ଟଙ୍କିଆ ମୁଦ୍ରା|एक रुपये का सिक्का|India 1 rupee coin
27_Currency|Two rupee coin|ଦୁଇ ଟଙ୍କିଆ ମୁଦ୍ରା|दो रुपये का सिक्का|India 2 rupee coin
27_Currency|Five rupee coin|ପାଞ୍ଚ ଟଙ୍କିଆ ମୁଦ୍ରା|पाँच रुपये का सिक्का|India 5 rupee coin
27_Currency|Ten rupee coin|ଦଶ ଟଙ୍କିଆ ମୁଦ୍ରା|दस रुपये का सिक्का|India 10 rupee coin
27_Currency|Twenty rupee coin|କୋଡ଼ିଏ ଟଙ୍କିଆ ମୁଦ୍ରା|बीस रुपये का सिक्का|India 20 rupee coin
27_Currency|Ten rupee note|ଦଶ ଟଙ୍କିଆ ନୋଟ|दस रुपये का नोट|India 10 rupee note
27_Currency|Twenty rupee note|କୋଡ଼ିଏ ଟଙ୍କିଆ ନୋଟ|बीस रुपये का नोट|India 20 rupee note
27_Currency|Fifty rupee note|ପଚାଶ ଟଙ୍କିଆ ନୋଟ|पचास रुपये का नोट|India 50 rupee note
27_Currency|Hundred rupee note|ଶହେ ଟଙ୍କିଆ ନୋଟ|सौ रुपये का नोट|India 100 rupee note
27_Currency|Two hundred rupee note|ଦୁଇଶହ ଟଙ୍କିଆ ନୋଟ|दो सौ रुपये का नोट|India 200 rupee note
27_Currency|Five hundred rupee note|ପାଞ୍ଚଶହ ଟଙ୍କିଆ ନୋଟ|पाँच सौ रुपये का नोट|India 500 rupee note
27_Currency|Fifty paise coin|ପଚାଶ ପଇସା ମୁଦ୍ରା|पचास पैसे का सिक्का|India 50 paise coin
27_Currency|Twenty five paise coin|ପଚିଶ ପଇସା ମୁଦ୍ରା|पच्चीस पैसे का सिक्का|India 25 paise coin
27_Currency|Ten paise coin|ଦଶ ପଇସା ମୁଦ୍ରା|दस पैसे का सिक्का|India 10 paise coin
27_Currency|One rupee note|ଏକ ଟଙ୍କିଆ ନୋଟ|एक रुपये का नोट|India 1 rupee note
27_Currency|Two rupee note|ଦୁଇ ଟଙ୍କିଆ ନୋଟ|दो रुपये का नोट|India 2 rupee note
27_Currency|Five rupee note|ପାଞ୍ଚ ଟଙ୍କିଆ ନୋଟ|पाँच रुपये का नोट|India 5 rupee note
27_Currency|Two thousand rupee note|ଦୁଇ ହଜାର ଟଙ୍କିଆ ନୋଟ|दो हज़ार रुपये का नोट|India 2000 rupee note
27_Currency|piggy bank|ଗୋଲକ|गुल्लक|piggy bank money
27_Currency|wallet|ପର୍ସ|बटुआ|wallet with money
27_Currency|ATM card|ଏଟିଏମ କାର୍ଡ|एटीएम कार्ड|ATM debit card
27_Currency|cheque|ଚେକ|चेक|bank cheque india
27_Currency|passbook|ପାସବୁକ|पासबुक|bank passbook india
27_Currency|bank|ବ୍ୟାଙ୍କ|बैंक|bank building india
27_Currency|ATM machine|ଏଟିଏମ ମେସିନ|एटीएम मशीन|ATM machine india
27_Currency|dollar note|ଡଲାର ନୋଟ|डॉलर नोट|US dollar banknote
27_Currency|coins|ମୁଦ୍ରା|सिक्के|indian coins collection
27_Currency|gold coin|ସୁନା ମୁଦ୍ରା|सोने का सिक्का|gold coin
27_Currency|QR code payment|କ୍ୟୁଆର କୋଡ ପେମେଣ୍ଟ|क्यूआर कोड भुगतान|UPI QR code payment
28_Countries|Afghanistan|ଆଫଗାନିସ୍ତାନ|अफ़ग़ानिस्तान|
28_Countries|Australia|ଅଷ୍ଟ୍ରେଲିଆ|ऑस्ट्रेलिया|
28_Countries|Bangladesh|ବାଂଲାଦେଶ|बांग्लादेश|
28_Countries|Bhutan|ଭୁଟାନ|भूटान|
28_Countries|Brazil|ବ୍ରାଜିଲ|ब्राज़ील|
28_Countries|Canada|କାନାଡା|कनाडा|
28_Countries|China|ଚୀନ|चीन|
28_Countries|France|ଫ୍ରାନ୍ସ|फ़्रांस|
28_Countries|Germany|ଜର୍ମାନୀ|जर्मनी|
28_Countries|India|ଭାରତ|भारत|
28_Countries|Iran|ଇରାନ|ईरान|
28_Countries|Italy|ଇଟାଲୀ|इटली|
28_Countries|Kenya|କେନିଆ|केन्या|
28_Countries|Malaysia|ମାଲେସିଆ|मलेशिया|
28_Countries|Myanmar|ମିଆଁମାର|म्यांमार|
28_Countries|Nepal|ନେପାଳ|नेपाल|
28_Countries|Pakistan|ପାକିସ୍ତାନ|पाकिस्तान|
28_Countries|Russia|ରୁଷିଆ|रूस|
28_Countries|South Africa|ଦକ୍ଷିଣ ଆଫ୍ରିକା|दक्षिण अफ्रीका|
28_Countries|Sri Lanka|ଶ୍ରୀଲଙ୍କା|श्रीलंका|
28_Countries|Turkey|ତୁର୍କୀ|तुर्की|
28_Countries|USA|ଆମେରିକା|अमेरिका|United States of America flag map
28_Countries|Japan|ଜାପାନ|जापान|
28_Countries|South Korea|ଦକ୍ଷିଣ କୋରିଆ|दक्षिण कोरिया|
28_Countries|Indonesia|ଇଣ୍ଡୋନେସିଆ|इंडोनेशिया|
28_Countries|Thailand|ଥାଇଲାଣ୍ଡ|थाईलैंड|
28_Countries|Vietnam|ଭିଏତନାମ|वियतनाम|
28_Countries|Singapore|ସିଙ୍ଗାପୁର|सिंगापुर|
28_Countries|Philippines|ଫିଲିପାଇନ୍ସ|फिलीपींस|
28_Countries|Maldives|ମାଲଦ୍ୱୀପ|मालदीव|
28_Countries|Saudi Arabia|ସାଉଦି ଆରବ|सऊदी अरब|
28_Countries|UAE|ସଂଯୁକ୍ତ ଆରବ ଏମିରେଟ୍ସ|संयुक्त अरब अमीरात|United Arab Emirates flag map
28_Countries|Iraq|ଇରାକ|इराक|
28_Countries|Israel|ଇସ୍ରାଏଲ|इज़राइल|
28_Countries|Egypt|ମିଶର|मिस्र|
28_Countries|Nigeria|ନାଇଜେରିଆ|नाइजीरिया|
28_Countries|Ethiopia|ଇଥିଓପିଆ|इथियोपिया|
28_Countries|Ghana|ଘାନା|घाना|
28_Countries|Morocco|ମୋରୋକ୍କୋ|मोरक्को|
28_Countries|United Kingdom|ଯୁକ୍ତରାଜ୍ୟ|यूनाइटेड किंगडम|United Kingdom flag map
28_Countries|Ireland|ଆୟର୍ଲ୍ୟାଣ୍ଡ|आयरलैंड|
28_Countries|Spain|ସ୍ପେନ|स्पेन|
28_Countries|Portugal|ପର୍ତ୍ତୁଗାଲ|पुर्तगाल|
28_Countries|Netherlands|ନେଦରଲ୍ୟାଣ୍ଡ|नीदरलैंड|
28_Countries|Switzerland|ସ୍ୱିଜରଲ୍ୟାଣ୍ଡ|स्विट्ज़रलैंड|
28_Countries|Sweden|ସ୍ୱିଡେନ|स्वीडन|
28_Countries|Norway|ନରୱେ|नॉर्वे|
28_Countries|Denmark|ଡେନମାର୍କ|डेनमार्क|
28_Countries|Finland|ଫିନଲ୍ୟାଣ୍ଡ|फ़िनलैंड|
28_Countries|Greece|ଗ୍ରୀସ|यूनान|
28_Countries|Poland|ପୋଲାଣ୍ଡ|पोलैंड|
28_Countries|Ukraine|ୟୁକ୍ରେନ|यूक्रेन|
28_Countries|Mexico|ମେକ୍ସିକୋ|मेक्सिको|
28_Countries|Argentina|ଆର୍ଜେଣ୍ଟିନା|अर्जेंटीना|
28_Countries|Cuba|କ୍ୟୁବା|क्यूबा|
28_Countries|Peru|ପେରୁ|पेरू|
28_Countries|Chile|ଚିଲି|चिली|
28_Countries|New Zealand|ନିଉଜିଲ୍ୟାଣ୍ଡ|न्यूज़ीलैंड|
28_Countries|Mongolia|ମଙ୍ଗୋଲିଆ|मंगोलिया|
28_Countries|Kazakhstan|କାଜାକସ୍ତାନ|कज़ाखस्तान|
28_Countries|Tanzania|ତାନଜାନିଆ|तंज़ानिया|
28_Countries|Kuwait|କୁଏତ|कुवैत|
28_Countries|Qatar|କତାର|क़तर|
28_Countries|Oman|ଓମାନ|ओमान|
29_Science_and_Space|A P J Abdul Kalam|ଏପିଜେ ଅବଦୁଲ କଲାମ|एपीजे अब्दुल कलाम|APJ Abdul Kalam
29_Science_and_Space|Aryabhata|ଆର୍ଯ୍ୟଭଟ୍ଟ|आर्यभट्ट|Aryabhata mathematician
29_Science_and_Space|asteroid|କ୍ଷୁଦ୍ରଗ୍ରହ|क्षुद्रग्रह|asteroid in space
29_Science_and_Space|Subhas Chandra Bose|ସୁଭାଷ ଚନ୍ଦ୍ର ବୋଷ|सुभाष चंद्र बोस|Netaji Subhas Chandra Bose
29_Science_and_Space|comet|ଧୂମକେତୁ|धूमकेतु|comet in space
29_Science_and_Space|Marie Curie|ମେରି କ୍ୟୁରି|मैरी क्यूरी|
29_Science_and_Space|C V Raman|ସି ଭି ରମଣ|सी वी रमन|C V Raman scientist
29_Science_and_Space|Charles Darwin|ଚାର୍ଲ୍ସ ଡାରୱିନ|चार्ल्स डार्विन|
29_Science_and_Space|Earth|ପୃଥିବୀ|पृथ्वी|planet earth from space
29_Science_and_Space|Albert Einstein|ଆଲବର୍ଟ ଆଇନଷ୍ଟାଇନ|अल्बर्ट आइंस्टीन|
29_Science_and_Space|galaxy|ଗ୍ୟାଲାକ୍ସି|मंदाकिनी|spiral galaxy
29_Science_and_Space|Galileo Galilei|ଗାଲିଲିଓ|गैलीलियो|Galileo Galilei
29_Science_and_Space|Jagadish Chandra Bose|ଜଗଦୀଶ ଚନ୍ଦ୍ର ବୋଷ|जगदीश चंद्र बोस|Jagadish Chandra Bose scientist
29_Science_and_Space|Jupiter|ବୃହସ୍ପତି|बृहस्पति|planet jupiter
29_Science_and_Space|Mars|ମଙ୍ଗଳ|मंगल|planet mars
29_Science_and_Space|Mercury|ବୁଧ|बुध|planet mercury
29_Science_and_Space|meteor|ଉଲ୍କା|उल्का|meteor shower
29_Science_and_Space|meteorite|ଉଲ୍କାପିଣ୍ଡ|उल्कापिंड|meteorite rock
29_Science_and_Space|moon|ଚନ୍ଦ୍ର|चाँद|moon in space
29_Science_and_Space|Neptune|ବରୁଣ|वरुण|planet neptune
29_Science_and_Space|Isaac Newton|ଆଇଜାକ ନିଉଟନ|आइज़ैक न्यूटन|Isaac Newton
29_Science_and_Space|Saturn|ଶନି|शनि|planet saturn
29_Science_and_Space|star|ତାରା|तारा|star in space
29_Science_and_Space|sun|ସୂର୍ଯ୍ୟ|सूरज|sun star
29_Science_and_Space|Nikola Tesla|ନିକୋଲା ଟେସଲା|निकोला टेस्ला|Nikola Tesla
29_Science_and_Space|Uranus|ୟୁରେନସ|अरुण|planet uranus
29_Science_and_Space|Venus|ଶୁକ୍ର|शुक्र|planet venus
29_Science_and_Space|Pluto|ପ୍ଲୁଟୋ|प्लूटो|Pluto dwarf planet
29_Science_and_Space|Milky Way|ଛାୟାପଥ|आकाशगंगा|Milky Way galaxy
29_Science_and_Space|solar system|ସୌରମଣ୍ଡଳ|सौरमंडल|solar system planets
29_Science_and_Space|planet|ଗ୍ରହ|ग्रह|planets in space
29_Science_and_Space|satellite|ଉପଗ୍ରହ|उपग्रह|artificial satellite in orbit
29_Science_and_Space|telescope|ଦୂରବୀକ୍ଷଣ ଯନ୍ତ୍ର|दूरबीन|astronomy telescope
29_Science_and_Space|microscope|ଅଣୁବୀକ୍ଷଣ ଯନ୍ତ୍ର|सूक्ष्मदर्शी|science microscope
29_Science_and_Space|Rakesh Sharma|ରାକେଶ ଶର୍ମା|राकेश शर्मा|Rakesh Sharma astronaut
29_Science_and_Space|Kalpana Chawla|କଳ୍ପନା ଚାୱଲା|कल्पना चावला|Kalpana Chawla astronaut
29_Science_and_Space|Sunita Williams|ସୁନିତା ୱିଲିୟମ୍ସ|सुनीता विलियम्स|Sunita Williams astronaut
29_Science_and_Space|Yuri Gagarin|ୟୁରୀ ଗାଗାରିନ|यूरी गागरिन|Yuri Gagarin
29_Science_and_Space|Neil Armstrong|ନିଲ ଆର୍ମଷ୍ଟ୍ରଙ୍ଗ|नील आर्मस्ट्रांग|Neil Armstrong astronaut
29_Science_and_Space|ISRO|ଇସ୍ରୋ|इसरो|ISRO India space agency
29_Science_and_Space|Chandrayaan|ଚନ୍ଦ୍ରଯାନ|चंद्रयान|Chandrayaan spacecraft
29_Science_and_Space|Mangalyaan|ମଙ୍ଗଳଯାନ|मंगलयान|Mangalyaan Mars Orbiter Mission
29_Science_and_Space|Aditya L1|ଆଦିତ୍ୟ ଏଲ୍ ୱାନ|आदित्य एल वन|Aditya L1 solar mission
29_Science_and_Space|Vikram Sarabhai|ବିକ୍ରମ ସାରାଭାଇ|विक्रम साराभाई|Vikram Sarabhai scientist
29_Science_and_Space|Homi Bhabha|ହୋମି ଭାବା|होमी भाभा|Homi Bhabha scientist
29_Science_and_Space|Srinivasa Ramanujan|ଶ୍ରୀନିବାସ ରାମାନୁଜନ|श्रीनिवास रामानुजन|Srinivasa Ramanujan mathematician
29_Science_and_Space|Stephen Hawking|ଷ୍ଟିଫେନ ହକିଙ୍ଗ|स्टीफन हॉकिंग|Stephen Hawking
29_Science_and_Space|Thomas Edison|ଥୋମାସ ଏଡିସନ|थॉमस एडिसन|Thomas Edison
29_Science_and_Space|Alexander Graham Bell|ଆଲେକ୍ସାଣ୍ଡର ଗ୍ରାହାମ ବେଲ|अलेक्जेंडर ग्राहम बेल|Alexander Graham Bell
29_Science_and_Space|Nicolaus Copernicus|କୋପରନିକସ|कोपरनिकस|Nicolaus Copernicus
29_Science_and_Space|Louis Pasteur|ଲୁଇ ପାଷ୍ଟର|लुई पाश्चर|Louis Pasteur
29_Science_and_Space|Wright Brothers|ରାଇଟ ଭାଇ|राइट बंधु|Wright Brothers airplane
29_Science_and_Space|black hole|କୃଷ୍ଣ ଗହ୍ୱର|ब्लैक होल|black hole space
29_Science_and_Space|solar eclipse|ସୂର୍ଯ୍ୟ ଗ୍ରହଣ|सूर्य ग्रहण|solar eclipse
29_Science_and_Space|lunar eclipse|ଚନ୍ଦ୍ର ଗ୍ରହଣ|चंद्र ग्रहण|lunar eclipse blood moon
29_Science_and_Space|rainbow|ଇନ୍ଦ୍ରଧନୁ|इंद्रधनुष|rainbow in sky
29_Science_and_Space|volcano|ଜ୍ୱାଳାମୁଖୀ|ज्वालामुखी|volcano eruption
29_Science_and_Space|lightning|ବିଜୁଳି|बिजली|lightning in sky
29_Science_and_Space|magnet|ଚୁମ୍ବକ|चुंबक|magnet iron filings
29_Science_and_Space|atom|ପରମାଣୁ|परमाणु|atom model science
29_Science_and_Space|DNA|ଡିଏନଏ|डीएनए|DNA double helix
29_Science_and_Space|gravity|ମାଧ୍ୟାକର୍ଷଣ|गुरुत्वाकर्षण|gravity apple falling
29_Science_and_Space|space station|ମହାକାଶ ଷ୍ଟେସନ|अंतरिक्ष स्टेशन|International Space Station
29_Science_and_Space|solar panel|ସୌର ପ୍ୟାନେଲ|सोलर पैनल|solar panel
29_Science_and_Space|constellation|ନକ୍ଷତ୍ରମଣ୍ଡଳ|तारामंडल|constellation stars night sky
29_Science_and_Space|pole star|ଧ୍ରୁବତାରା|ध्रुव तारा|pole star north star
"""

# ---------------- built-in copy of the GoogleImage.java name table ----------------
FIX = {
    'ctagon': 'octagon',
    'golden': 'golden|golden color',
    'gray': 'gray|gray color',
    'betelnut': 'betel nut|betel nut areca',
    'dates dried': 'dried dates',
    'flexseeds': 'flax seeds',
    'groundnut': 'groundnut|peanut',
    'litchi': 'litchi|lychee fruit',
    'sapodilla': 'sapodilla|sapodilla chikoo fruit',
    'walnuts': 'walnuts|walnut',
    'beans': 'beans|green beans vegetable',
    'chilly': 'chilly|green chilli',
    'frenchbeans': 'french beans',
    'ladyfinger': 'ladyfinger|okra ladyfinger vegetable',
    'parwal': 'parwal|pointed gourd parwal vegetable',
    'peas': 'peas|green peas vegetable',
    'pumpkin seeds': 'pumpkin seeds|pumpkin seeds food',
    'butterflypea': 'butterfly pea|butterfly pea flower',
    'champak': 'champak|champak flower',
    'datura': 'datura|datura flower',
    'gardendaisy': 'garden daisy|daisy flower',
    'goldmohur': 'gold mohur|gulmohar flower',
    'lilly': 'lily|lily flower',
    'lotuss': 'lotus|lotus flower',
    'moonbeam': 'moonbeam|moonbeam flower',
    'saffron': 'saffron|saffron crocus flower',
    'tuberose': 'tuberose|tuberose flower',
    'bulbul': 'bulbul|bulbul bird',
    'cock': 'cock|rooster',
    'cuckoo': 'cuckoo|cuckoo bird',
    'gander': 'gander|goose bird',
    'gharachatia': 'gharachatia|house sparrow bird',
    'hansa': 'hansa|swan bird',
    'hen': 'hen|hen chicken',
    'kau': 'kau|crow bird',
    'macharanka': 'macharanka|kingfisher bird',
    'mayuri': 'mayuri|peahen bird',
    'pecha': 'pecha|owl bird',
    'termite': 'termite|termite insect',
    'ant': 'ant|ant insect',
    'bee': 'bee|honey bee insect',
    'seal': 'seal|seal sea animal',
    'eel': 'eel|eel fish',
    'iron': 'iron|clothes iron electric',
    'cooker': 'cooker|pressure cooker kitchen',
    'dustbin': 'dustbin|dustbin trash can',
    'gasstove': 'gas stove',
    'aeroplane': 'aeroplane|aeroplane airplane flying',
    'fighterplane': 'fighter plane|fighter jet',
    'jcb': 'JCB|JCB excavator',
    'tank': 'tank|army battle tank',
    'water scooter': 'water scooter|jet ski water scooter',
    'bullock cart': 'bullock cart|bullock cart india',
    'auto rickshaw': 'auto rickshaw|auto rickshaw india',
    'police': 'police|police officer',
    'painter': 'painter|house wall painter',
    'potter': 'potter|potter making clay pot',
    'builder': 'builder|construction worker builder',
    'scientist': 'scientist|scientist laboratory',
    'cpu': 'CPU|computer cpu cabinet',
    'ups': 'UPS|UPS uninterruptible power supply for computer',
    'webcamera': 'web camera|webcam',
    'pendrive': 'pen drive|usb pen drive',
    'speakers': 'speakers|computer speakers',
    'buddhapurnima': 'Buddha Purnima|Buddha Purnima festival',
    'dasahera': 'Dasahera|Dussehra festival',
    'diwali': 'Diwali|Diwali festival',
    'eid': 'Eid|Eid festival',
    'holi': 'Holi|Holi festival colors',
    'indipendenceday': 'Independence Day|India Independence Day',
    'janmastami': 'Janmashtami|Janmashtami festival',
    'kartikapurnima': 'Kartika Purnima|Kartika Purnima Boita Bandana Cuttack',
    'kumarapurnima': 'Kumara Purnima|Kumar Purnima Odisha festival',
    'nuakhai': 'Nuakhai|Nuakhai festival Odisha',
    'rakshabandhan': 'Raksha Bandhan|Raksha Bandhan festival rakhi',
    'rathayatra': 'Rath Yatra|Rath Yatra Puri Jagannath',
    'republicday': 'Republic Day|India Republic Day parade',
    'shivaratri': 'Shivaratri|Maha Shivaratri',
    'xmass': 'Christmas|Christmas festival',
    'c1': 'One rupee coin|India 1 rupee coin',
    'c2': 'Two rupee coin|India 2 rupee coin',
    'c3': 'Five rupee coin|India 5 rupee coin',
    'c4': 'Ten rupee coin|India 10 rupee coin',
    'c5': 'Twenty rupee coin|India 20 rupee coin',
    'c6': 'Ten rupee note|India 10 rupee note',
    'c7': 'Twenty rupee note|India 20 rupee note',
    'c8': 'Fifty rupee note|India 50 rupee note',
    'c9': 'Hundred rupee note|India 100 rupee note',
    'c10': 'Two hundred rupee note|India 200 rupee note',
    'c11': 'Five hundred rupee note|India 500 rupee note',
    'mianmar': 'Myanmar',
    'usa': 'USA|United States of America',
    'southafrica': 'South Africa',
    'srilanka': 'Sri Lanka',
    'apj': 'A P J Abdul Kalam|APJ Abdul Kalam',
    'aryabhat': 'Aryabhata|Aryabhata mathematician',
    'bose': 'Subhas Chandra Bose|Netaji Subhas Chandra Bose',
    'cvraman': 'C V Raman|C V Raman scientist',
    'jagdish bose': 'Jagadish Chandra Bose|Jagadish Chandra Bose scientist',
    'curie': 'Marie Curie',
    'darwin': 'Charles Darwin',
    'einstein': 'Albert Einstein',
    'galilei': 'Galileo Galilei',
    'newton': 'Isaac Newton',
    'tesla': 'Nikola Tesla',
    'earth': 'earth|planet earth from space',
    'jupiter': 'jupiter|planet jupiter',
    'mars': 'mars|planet mars',
    'mercury': 'mercury|planet mercury',
    'neptune': 'neptune|planet neptune',
    'saturn': 'saturn|planet saturn',
    'uranus': 'uranus|planet uranus',
    'venus': 'venus|planet venus',
    'moon': 'moon|moon in space',
    'sun': 'sun|sun star',
    'star': 'star|star in space',
    'asteroid': 'asteroid|asteroid in space',
    'comet': 'comet|comet in space',
    'meteor': 'meteor|meteor shower',
    'meteorite': 'meteorite|meteorite rock',
    'galaxy': 'galaxy|spiral galaxy',
}

# ---------------- read SeeData.java / GoogleImage.java (when they are next to this script) ----------------
def parse_seedata(text):
    """-> (folders in order, {folder: [(english, odia, hindi, hint), ...]})"""
    arrays = {}
    for m in re.finditer(r'String\[\]\s+(\w+)\s*=\s*\{(.*?)\};', text, re.S):
        arrays[m.group(1)] = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))
    folders, words = [], {}
    for m in re.finditer(r'\badd\(\s*"([^"]+)"\s*,\s*(\w+)\s*\)', text):
        folder, arr = m.group(1), m.group(2)
        items = []
        for line in arrays.get(arr, []):
            p = line.split("|")
            while p and p[-1] == "": p.pop()                       # Java split() drops empty tail parts
            if len(p) < 3: continue
            items.append((p[0], p[1], p[2], p[3] if len(p) > 3 and p[3] else ""))
        folders.append(folder); words[folder] = items
    return folders, words

def parse_fix(text):
    return {m.group(1): m.group(2) for m in re.finditer(r'FIX\.put\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)', text)}

def embedded_words():
    folders, words = [], {}
    for l in DATA.strip().split("\n"):
        f, en, od, hi, hint = l.split("|", 4)
        if f not in words: folders.append(f); words[f] = []
        words[f].append((en, od, hi, hint))
    return folders, words

FOLDERS, WORDS_BY_FOLDER = embedded_words()
if os.path.exists(SEE_JAVA):
    try:
        f, w = parse_seedata(open(SEE_JAVA, encoding="utf-8").read())
        if f: FOLDERS, WORDS_BY_FOLDER = f, w; print("Word list read from", SEE_JAVA)
    except Exception as e:
        print("could not read", SEE_JAVA, "->", e, "(built-in list is used)")
if os.path.exists(GOOGLE_JAVA):
    try:
        fx = parse_fix(open(GOOGLE_JAVA, encoding="utf-8").read())
        if fx: FIX = fx; print("Name table read from", GOOGLE_JAVA)
    except Exception as e:
        print("could not read", GOOGLE_JAVA, "->", e, "(built-in table is used)")

# ---------------- search words: exactly GoogleImage.queryFor() ----------------
CONTEXT = [("color", " color"), ("shape", " shape geometry"), ("fruit", " fruit"), ("vegetable", " vegetable"), ("flower", " flower"),
           ("animal", " animal"), ("body", " human body part"), ("emotion", " emotion child face"), ("household", " household"),
           ("transport", " vehicle"), ("profession", " profession"), ("computer", " computer"), ("countr", " country flag map"),
           ("festival", " festival india"), ("currency", " india currency"), ("science", " science")]

def add_context(q, folder, full):
    if full: return q
    f = folder.lower()
    for key, add in CONTEXT:
        if key in f: return q + add
    return q

def query_for(folder, en, hint):
    if hint: return hint                                            # 1) search words written in SeeData
    f = FIX.get(en.lower())                                         # 2) the name table
    if f is not None:
        bar = f.find("|")
        return add_context(f[bar + 1:] if bar >= 0 else f, folder, bar >= 0)
    return add_context(en, folder, False)                           # 3) the word + the kind of chapter

# ---------------- Bing + pictures (same as GoogleImage) ----------------
SEARCH_SEM = threading.Semaphore(SEARCH_PARALLEL)

def http(url, timeout=12, maxb=4 * 1024 * 1024, accept=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+cb; SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"}
    if accept: h["Accept"] = accept
    with urllib.request.build_opener().open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read(maxb + 1)
        if len(data) > maxb: raise ValueError("too big")
        return data, r.headers.get("Content-Type", "")

def unescape(s):
    return (s.replace("\\u003d", "=").replace("\\u0026", "&").replace("\\u003f", "?").replace("\\u002f", "/")
             .replace("\\/", "/").replace("&amp;", "&").replace("\\\\", "\\"))

def search_urls(query, page):
    """picture addresses of one Bing Images result page, best first"""
    with SEARCH_SEM:
        html, _ = http("https://www.bing.com/images/search?adlt=strict&form=HDRSC3&first=" + str(1 + PAGE_STEP * page)
                       + "&q=" + urllib.parse.quote(query), maxb=3 * 1024 * 1024)
    html = html.decode("utf-8", "ignore"); out = []
    for m in re.finditer(r'murl(?:&quot;|")\s*:\s*(?:&quot;|")(https?:[^"<>\s]+?)(?:&quot;|")', html):
        u = unescape(m.group(1))
        if u not in out: out.append(u)
        if len(out) >= CANDIDATES: break
    return out

def fetch_picture(url):
    """downloaded picture -> PIL image (RGB, transparent parts on white, longest side <= STORE_PX) or None"""
    try:
        data, ctype = http(url, timeout=10, accept="image/*")
        if ctype and not ctype.lower().startswith("image/"): return None
        im = Image.open(io.BytesIO(data)); im.load()
        if im.width < MIN_SIDE or im.height < MIN_SIDE: return None
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((STORE_PX, STORE_PX))
        return im
    except Exception:
        return None

def ahash(im):
    g = im.convert("L").resize((8, 8)); px = list(g.tobytes()); avg = sum(px) / 64.0
    return sum(1 << i for i, v in enumerate(px) if v > avg)

def same(a, b):
    return bin(a ^ b).count("1") <= 4                               # only to skip the SAME picture twice

img_pool = ThreadPoolExecutor(IMG_WORKERS)

# ---------------- one word ----------------
class W:
    def __init__(s, folder, item):
        s.chapter, (s.en, s.od, s.hi, s.hint) = folder, item
        s.q = query_for(folder, s.en, s.hint)
        s.key = "%s|%s|%s" % (folder, s.en, s.q)                    # changed search words = a new word -> downloaded again
        s.name = re.sub(r'[\\/:*?"<>|]', "", "%s_%s_%s" % (s.en, s.od, s.hi)).strip()
        s.out = os.path.join(OUT, folder, s.name + ".webp")         # same shape as SeeData paths: folder/english_odia_hindi.webp
        s.n, s.err, s.complete = 0, "", False

def to_tile(im):
    """whole picture (no cropping) centred on a white TILE x TILE square"""
    s = float(TILE) / max(im.size)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    tile = Image.new("RGB", (TILE, TILE), (255, 255, 255))
    tile.paste(im, ((TILE - im.width) // 2, (TILE - im.height) // 2))
    return tile

def merge4(tiles):
    n = min(len(tiles), 4)                                          # 1 picture: single, 2: side by side, 3-4: 2x2
    cols = 1 if n == 1 else 2
    rows = 1 if n <= 2 else 2
    sheet = Image.new("RGB", (TILE * cols, TILE * rows), (255, 255, 255))
    for i, t in enumerate(tiles[:4]):
        sheet.paste(t, ((i % 2) * TILE, (i // 2) * TILE))
    buf = io.BytesIO(); sheet.save(buf, "WEBP", quality=QUALITY, method=6)
    return buf.getvalue()

def do_word(w):
    """GoogleImage.ensureSet(): search, then the first pictures are downloaded all at once (+1 spare), in search order, until 4 are there"""
    got, hashes, seen = [], [], set()
    page, fails, exhausted = 0, 0, False
    while len(got) < GRID and page < MAX_PAGES:
        try:
            urls = search_urls(w.q, page)
        except Exception as e:
            fails += 1; w.err = "search: %s" % e
            if fails >= 3: break
            time.sleep(1.5 * fails + random.random()); continue
        fails = 0
        urls = [u for u in urls if u not in seen]
        if not urls:
            w.err = w.err or "Bing gave no pictures"; exhausted = True; break
        w.err = ""; seen.update(urls); i = 0
        while len(got) < GRID and i < len(urls):
            batch = urls[i:i + (GRID - len(got)) + 1]; i += len(batch)
            for im in img_pool.map(fetch_picture, batch):             # map() keeps the search order
                if im is None or len(got) >= GRID: continue
                h = ahash(im)
                if any(same(h, o) for o in hashes): continue
                hashes.append(h); got.append(im)
        page += 1
    if got:
        os.makedirs(os.path.dirname(w.out), exist_ok=True)
        open(w.out, "wb").write(merge4([to_tile(im) for im in got]))
    elif not w.err:
        w.err = "pictures found but could not be downloaded"
    w.n = len(got)
    w.complete = len(got) >= GRID or exhausted or page >= MAX_PAGES   # otherwise (network problem) it is tried again next run

# ---------------- state / resume ----------------
if os.path.exists("assets.zip") and not os.path.isdir(OUT) and not FRESH:        # old result next to the script -> resume
    try:
        zipfile.ZipFile("assets.zip").extractall("."); print("Old assets.zip unpacked -> only unfinished words are downloaded")
    except Exception as e:
        print("could not unpack old assets.zip:", e)
if FRESH:
    shutil.rmtree(OUT, ignore_errors=True)
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
STATE = {}
if os.path.exists(STATE_FILE):
    try: STATE = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception: STATE = {}
STATE_LOCK = threading.Lock()
def save_state():
    with STATE_LOCK:
        json.dump(STATE, open(STATE_FILE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(STATE_FILE + ".tmp", STATE_FILE)

words = [W(f, it) for f in FOLDERS for it in WORDS_BY_FOLDER.get(f, [])]
redo = set(x.lower() for x in REDO)
for w in words:
    st = STATE.get(w.key)
    if st and st.get("complete") and os.path.exists(w.out) and w.en.lower() not in redo:
        w.n, w.complete, w.err = st.get("n", 0), True, st.get("err", "")
        w.skipped = True
    else:
        w.skipped = False
print("Words: %d in %d chapters | already done: %d | to download now: %d" % (
      len(words), len(FOLDERS), sum(1 for w in words if w.skipped), sum(1 for w in words if not w.skipped)))

# ================================ chapter by chapter (all words of a chapter at the same time) ================================
t0 = time.time()
for folder in FOLDERS:
    todo = [w for w in words if w.chapter == folder and not w.skipped]
    total = sum(1 for w in words if w.chapter == folder)
    if not todo:
        print("%-22s all %d words already done" % (folder, total)); continue
    tc, done = time.time(), 0
    with ThreadPoolExecutor(WORD_WORKERS) as wp:
        futs = {wp.submit(do_word, w): w for w in todo}
        for f in as_completed(futs):
            w = futs[f]
            try: f.result()
            except Exception as e: w.err = "error: %s" % e
            with STATE_LOCK:
                STATE[w.key] = {"n": w.n, "complete": w.complete, "err": w.err, "q": w.q}
            done += 1
    save_state()
    full = sum(1 for w in todo if w.n >= GRID); part = sum(1 for w in todo if 0 < w.n < GRID); none = sum(1 for w in todo if w.n == 0)
    print("%-22s %d words: %d with 4 pictures, %d with 1-3, %d without  [%.0f s]" % (folder, len(todo), full, part, none, time.time() - tc))

# ================================ report + zip ================================
report = []
for w in words:
    st = "OK" if w.n >= GRID else ("PARTIAL" if w.n else "FAILED")
    report.append([w.chapter, w.en, w.od, w.hi, st, w.n, w.q, w.err])
with open(REPORT, "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([["chapter", "english", "odia", "hindi", "status", "pictures", "search_words", "error"]] + report)
miss = [r for r in report if r[4] != "OK"]
print("\nFinished in %.1f min: %d words with 4 pictures, %d with fewer" % ((time.time() - t0) / 60, len(report) - len(miss), len(miss)))
for r in miss: print("  fewer than 4:", r[0], r[1], "|", r[6], "|", r[5], "pictures", r[7])
if miss: print("-> run again: ONLY these words are downloaded again (or change their search words in SeeData.java)")

with zipfile.ZipFile("assets.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for root, ds, fs in os.walk(OUT):
        for fn in sorted(fs):
            p = os.path.join(root, fn); z.write(p, p.replace(os.sep, "/"))
    z.write(REPORT); z.write(STATE_FILE)
print("assets.zip: %.1f MB" % (os.path.getsize("assets.zip") / 1048576))
try:
    from google.colab import files
    files.download("assets.zip")
except ImportError:
    print("Not in Colab: assets.zip is in the current folder")
