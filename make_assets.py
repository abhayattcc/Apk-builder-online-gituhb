# === ONE cell (Colab or GitHub Actions) ==========================================================================
# SEARCH   Bing Images, ONE simple search term per word (the last column of the word list below), e.g.  "a p j abdul kalam"  /  "apple fruit"  /  "black color"
#          -> no chapter prefix, no "only", no rotating wordings. If a word needs more pictures, the SAME term is searched on the next Bing page.
# CHECK    VERIFY = True: every picture is checked by CLIP right after its download (per word, in small chunks, while other words keep downloading).
#          Only pictures that EXACTLY match the word are kept; the word stops as soon as it has 4 exact pictures.
# RESUME   state.json + assets/ remember every word. On the next run ONLY words that are not verified (OK) are downloaded and checked again,
#          and they continue on deeper Bing pages. Verified words are never touched. (Colab: upload your old assets.zip next to this file.)
#          Force a redo of single words with REDO = ["apple", "rose"]  (english names), or everything with FRESH = True.
# MERGE    the exact pictures of each word are merged DIRECTLY into one 2x2 WebP, written immediately when the word is finished
#          -> assets.zip (assets/<chapter>/*.webp + verify_report.csv + state.json)
import subprocess, sys
VERIFY = True            # True = only exact-match pictures. False = take the first 4 pictures Bing gives (fastest)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"] + (["transformers"] if VERIFY else []), check=False)

import io, os, re, time, csv, json, uuid, random, shutil, zipfile, hashlib, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

REDO = []                # english names to force again, e.g. ["apple", "A P J Abdul Kalam"]
FRESH = False            # True = ignore all old results and start from zero
CHUNK = 8                # pictures downloaded + checked together (a word stops after the chunk in which it reaches 4 exact pictures)
WORD_WORKERS = 48        # words processed at the same time (all chapters together)
IMG_WORKERS = 160        # picture downloads at the same time
SEARCH_PARALLEL = 12     # Bing search pages requested at the same time
MAX_PAGES = 6            # Bing pages tried per word and run (same search term, deeper results). A later run continues after these.
GRID, TILE, QUALITY = 4, 300, 50   # 4 pictures, 300 px tiles -> 600x600 merged WebP (small files)
MIN_SIDE = 150           # smaller pictures are rejected
CLIP_MODEL = "openai/clip-vit-base-patch16"   # or "openai/clip-vit-base-patch32" for more speed
GOOD_PROB = 0.25         # exact match = CLIP gives the word at least this probability and it is #1 in its chapter
CACHE_KEEP, OUT, STATE_FILE = "keep", "assets", "state.json"
PHOTO_CHAPTERS = ("fruit", "vegetable", "flower", "animal", "household", "transport", "profession", "computer", "body")

# chapter|english|odia|hindi|SEARCH TERM (one simple term, also the text the checker compares the pictures with)
DATA = """
07_Colors|black|କଳା|काला|black color
07_Colors|blue|ନୀଳ|नीला|blue color
07_Colors|brown|ବାଦାମୀ|भूरा|brown color
07_Colors|golden|ସୁନେଲି|सुनहरा|golden color
07_Colors|gray|ଧୂସର|स्लेटी|gray color
07_Colors|green|ସବୁଜ|हरा|green color
07_Colors|navy blue|ଗାଢ଼ ନୀଳ|गहरा नीला|navy blue color
07_Colors|orange|କମଳା|नारंगी|orange color
07_Colors|pink|ଗୋଲାପି|गुलाबी|pink color
07_Colors|red|ନାଲି|लाल|red color
07_Colors|violet|ବାଇଗଣୀ|बैंगनी|violet color
07_Colors|white|ଧଳା|सफेद|white color
07_Colors|yellow|ହଳଦିଆ|पीला|yellow color
07_Colors|maroon|ମାରୁନ|मरून|maroon color
07_Colors|sky blue|ଆକାଶୀ ନୀଳ|आसमानी|sky blue color
07_Colors|light blue|ହାଲୁକା ନୀଳ|हल्का नीला|light blue color
07_Colors|light green|ହାଲୁକା ସବୁଜ|हल्का हरा|light green color
07_Colors|dark green|ଗାଢ଼ ସବୁଜ|गहरा हरा|dark green color
07_Colors|silver|ରୂପେଲି|रुपहला|silver color
07_Colors|cream|କ୍ରିମ|क्रीम|cream color
07_Colors|beige|ବେଜ|बेज|beige color
07_Colors|turquoise|ଫିରୋଜା|फ़िरोज़ी|turquoise color
07_Colors|lavender|ଲ୍ୟାଭେଣ୍ଡର|लैवेंडर|lavender color
07_Colors|peach|ପିଚ୍|पीच|peach color
07_Colors|magenta|ମେଜେଣ୍ଟା|मैजेंटा|magenta color
07_Colors|coral|କୋରାଲ|मूंगा|coral color
07_Colors|mustard|ସୋରିଷ ରଙ୍ଗ|सरसों|mustard color
07_Colors|olive green|ଅଲିଭ ସବୁଜ|जैतूनी हरा|olive green color
07_Colors|bronze|ବ୍ରୋଞ୍ଜ|काँस्य|bronze color
07_Colors|rainbow|ଇନ୍ଦ୍ରଧନୁ|इंद्रधनुष|rainbow
07_Colors|multicolor|ବହୁରଙ୍ଗୀ|बहुरंगी|multicolor
08_Shapes|circle|ବୃତ୍ତ|वृत्त|circle shape
08_Shapes|cone|ଶଙ୍କୁ|शंकु|cone shape
08_Shapes|octagon|ଅଷ୍ଟଭୁଜ|अष्टभुज|octagon shape
08_Shapes|cube|ଘନ|घन|cube shape
08_Shapes|cylinder|ସ୍ତମ୍ଭ|बेलन|cylinder shape
08_Shapes|hexagon|ଷଡ଼ଭୁଜ|षट्भुज|hexagon shape
08_Shapes|oval|ଅଣ୍ଡାକାର|अंडाकार|oval shape
08_Shapes|pentagon|ପଞ୍ଚଭୁଜ|पंचभुज|pentagon shape
08_Shapes|prism|ପ୍ରିଜ୍ମ|प्रिज्म|prism shape
08_Shapes|rectangle|ଆୟତ|आयत|rectangle shape
08_Shapes|rhombus|ସମଚତୁର୍ଭୁଜ|समचतुर्भुज|rhombus shape
08_Shapes|square|ବର୍ଗ|वर्ग|square shape
08_Shapes|triangle|ତ୍ରିଭୁଜ|त्रिभुज|triangle shape
08_Shapes|heart|ହୃଦୟ|दिल|heart shape
08_Shapes|star|ତାରା|तारा|star shape
08_Shapes|crescent|ଅର୍ଦ୍ଧଚନ୍ଦ୍ର|अर्धचंद्र|crescent shape
08_Shapes|sphere|ଗୋଲକ|गोला|sphere shape
08_Shapes|pyramid|ପିରାମିଡ୍|पिरामिड|pyramid shape
08_Shapes|trapezium|ସମଲମ୍ବ ଚତୁର୍ଭୁଜ|समलंब चतुर्भुज|trapezium shape
08_Shapes|parallelogram|ସମାନ୍ତର ଚତୁର୍ଭୁଜ|समांतर चतुर्भुज|parallelogram shape
08_Shapes|semicircle|ଅର୍ଦ୍ଧବୃତ୍ତ|अर्धवृत्त|semicircle shape
08_Shapes|ring|ବଳୟ|छल्ला|ring shape
08_Shapes|diamond|ହୀରକ ଆକାର|हीरे का आकार|diamond shape
08_Shapes|cuboid|ଆୟତଘନ|घनाभ|cuboid shape
08_Shapes|heptagon|ସପ୍ତଭୁଜ|सप्तभुज|heptagon shape
08_Shapes|decagon|ଦଶଭୁଜ|दशभुज|decagon shape
08_Shapes|hemisphere|ଅର୍ଦ୍ଧଗୋଲକ|अर्धगोला|hemisphere shape
08_Shapes|arrow|ତୀର|तीर|arrow shape
08_Shapes|cross|କ୍ରସ|क्रॉस|cross shape
08_Shapes|line|ସରଳ ରେଖା|रेखा|straight line
08_Shapes|curve|ବକ୍ର ରେଖା|वक्र रेखा|curve shape
08_Shapes|spiral|ସର୍ପିଳ|सर्पिल|spiral shape
08_Shapes|kite|ଘୁଡ଼ି ଆକାର|पतंग आकार|kite shape
09_Fruits|almond|ବାଦାମ|बादाम|almond nuts
09_Fruits|apple|ସେଓ|सेब|apple fruit
09_Fruits|banana|କଦଳୀ|केला|banana
09_Fruits|betel nut|ଗୁଆ|सुपारी|betel nut
09_Fruits|blackberry|କଳା ବେରି|ब्लैकबेरी|blackberry
09_Fruits|cashew nut|କାଜୁ|काजू|cashew nuts
09_Fruits|cherry|ଚେରି|चेरी|cherry fruit
09_Fruits|coconut|ନଡ଼ିଆ|नारियल|coconut
09_Fruits|custard apple|ସୀତାଫଳ|सीताफल|custard apple
09_Fruits|dried dates|ଛୁହାରା|छुहारा|dried dates
09_Fruits|flax seeds|ଅଳସି|अलसी|flax seeds
09_Fruits|grapes|ଅଙ୍ଗୁର|अंगूर|grapes
09_Fruits|groundnut|ଚିନାବାଦାମ|मूंगफली|peanut
09_Fruits|guava|ପିଜୁଳି|अमरूद|guava
09_Fruits|jackfruit|ପଣସ|कटहल|jackfruit
09_Fruits|kiwi|କିୱି|कीवी|kiwi fruit
09_Fruits|lemon|ଲେମ୍ବୁ|नींबू|lemon
09_Fruits|litchi|ଲିଚି|लीची|lychee
09_Fruits|mango|ଆମ୍ବ|आम|mango
09_Fruits|muskmelon|ଖରଭୁଜ|खरबूजा|muskmelon
09_Fruits|orange|କମଳା|संतरा|orange fruit
09_Fruits|papaya|ଅମୃତଭଣ୍ଡା|पपीता|papaya
09_Fruits|pear|ନାସପାତି|नाशपाती|pear fruit
09_Fruits|pineapple|ଅନାନାସ|अनानास|pineapple
09_Fruits|pistachio|ପିସ୍ତା|पिस्ता|pistachio
09_Fruits|pomegranate|ଡାଳିମ୍ବ|अनार|pomegranate
09_Fruits|raisin|କିସମିସ|किशमिश|raisins
09_Fruits|sapodilla|ସପୋଟା|चीकू|chikoo
09_Fruits|sugarcane|ଆଖୁ|गन्ना|sugarcane
09_Fruits|tamarind|ତେନ୍ତୁଳି|इमली|tamarind
09_Fruits|walnuts|ଆଖରୋଟ|अखरोट|walnuts
09_Fruits|watermelon|ତରଭୁଜ|तरबूज|watermelon
09_Fruits|apricot|ଖୁବାନି|खुबानी|apricot
09_Fruits|plum|ଆଳୁବୁଖରା|आलूबुखारा|plum fruit
09_Fruits|peach|ପିଚ୍|आड़ू|peach fruit
09_Fruits|strawberry|ଷ୍ଟ୍ରବେରି|स्ट्रॉबेरी|strawberry
09_Fruits|blueberry|ବ୍ଲୁବେରି|ब्लूबेरी|blueberry
09_Fruits|raspberry|ରାସବେରି|रास्पबेरी|raspberry
09_Fruits|mulberry|ତୁତ|शहतूत|mulberry
09_Fruits|gooseberry|ଅଁଳା|आंवला|amla
09_Fruits|black plum|ଜାମୁ|जामुन|jamun
09_Fruits|wood apple|କଇଥ|कैथ|wood apple
09_Fruits|bael|ବେଲ|बेल|bael fruit
09_Fruits|star fruit|କର୍ମଙ୍ଗା|कमरख|star fruit
09_Fruits|fig|ଡିମ୍ବିରି|अंजीर|fig fruit
09_Fruits|dragon fruit|ଡ୍ରାଗନ ଫ୍ରୁଟ|ड्रैगन फ्रूट|dragon fruit
09_Fruits|avocado|ଆଭୋକାଡୋ|एवोकाडो|avocado
09_Fruits|sweet lime|ମୋସମ୍ବି|मौसंबी|mosambi
09_Fruits|grapefruit|ଗ୍ରେପ୍‌ଫ୍ରୁଟ|चकोतरा|grapefruit
09_Fruits|passion fruit|ପାସନ ଫ୍ରୁଟ|पैशन फ्रूट|passion fruit
09_Fruits|cranberry|କ୍ରାନବେରି|क्रैनबेरी|cranberry
09_Fruits|jujube|ବରକୋଳି|बेर|ber fruit
09_Fruits|dates|ଖଜୁରୀ|खजूर|dates fruit
09_Fruits|chestnut|ଚେଷ୍ଟନଟ୍|चेस्टनट|chestnut
09_Fruits|olive|ଜଳପାଇ|जैतून|olive fruit
09_Fruits|persimmon|ପର୍ସିମନ|पर्सिमन|persimmon
09_Fruits|nectarine|ନେକ୍ଟାରିନ|नेक्टराइन|nectarine
09_Fruits|tangerine|ଟାଞ୍ଜେରିନ|टैंजेरीन|tangerine
09_Fruits|honeydew melon|ହନିଡ୍ୟୁ ମେଲନ|हनीड्यू खरबूजा|honeydew melon
09_Fruits|fox nut|ମଖାନା|मखाना|makhana
09_Fruits|hazelnut|ହେଜେଲନଟ୍|हेज़लनट|hazelnut
09_Fruits|palmyra fruit|ତାଳ|ताड़ का फल|palmyra fruit
09_Fruits|dry fruits|ଶୁଖିଲା ଫଳ|सूखे मेवे|dry fruits
10_Vegetables|beans|ବିନ୍ସ|बीन्स|green beans
10_Vegetables|beetroot|ବିଟ|चुकंदर|beetroot
10_Vegetables|bitter gourd|କଲରା|करेला|bitter gourd
10_Vegetables|bottle gourd|ଲାଉ|लौकी|bottle gourd
10_Vegetables|brinjal|ବାଇଗଣ|बैंगन|brinjal
10_Vegetables|broccoli|ବ୍ରୋକୋଲି|ब्रोकली|broccoli
10_Vegetables|cabbage|ବନ୍ଧାକୋବି|पत्ता गोभी|cabbage
10_Vegetables|capsicum|କ୍ୟାପ୍ସିକମ|शिमला मिर्च|capsicum
10_Vegetables|carrot|ଗାଜର|गाजर|carrot
10_Vegetables|cauliflower|ଫୁଲକୋବି|फूलगोभी|cauliflower
10_Vegetables|chilly|ଲଙ୍କା|मिर्च|green chilli
10_Vegetables|coriander|ଧନିଆ|धनिया|coriander leaves
10_Vegetables|corn|ମକା|मक्का|corn cob
10_Vegetables|cucumber|କାକୁଡ଼ି|खीरा|cucumber
10_Vegetables|curry leaf|ଭୃଷଙ୍ଗ|करी पत्ता|curry leaves
10_Vegetables|french beans|ଫ୍ରେଞ୍ଚ ବିନ୍ସ|फ्रेंच बीन्स|french beans
10_Vegetables|garlic|ରସୁଣ|लहसुन|garlic
10_Vegetables|ginger|ଅଦା|अदरक|ginger
10_Vegetables|ladyfinger|ଭେଣ୍ଡି|भिंडी|okra
10_Vegetables|mushroom|ଛତୁ|मशरूम|mushroom
10_Vegetables|onion|ପିଆଜ|प्याज|onion
10_Vegetables|parwal|ପୋଟଳ|परवल|parwal
10_Vegetables|peas|ମଟର|मटर|green peas
10_Vegetables|potato|ଆଳୁ|आलू|potato
10_Vegetables|pumpkin seeds|କଖାରୁ ବିହନ|कद्दू के बीज|pumpkin seeds
10_Vegetables|pumpkin|କଖାରୁ|कद्दू|pumpkin
10_Vegetables|radish|ମୂଳା|मूली|radish
10_Vegetables|spinach|ପାଳଙ୍ଗ|पालक|spinach
10_Vegetables|sweet potato|ରଙ୍ଗା ଆଳୁ|शकरकंद|sweet potato
10_Vegetables|tomato|ଟମାଟୋ|टमाटर|tomato
10_Vegetables|lettuce|ଲେଟୁସ|सलाद पत्ता|lettuce
10_Vegetables|celery|ସେଲେରି|अजमोदा|celery
10_Vegetables|turnip|ଶଳଗମ|शलजम|turnip
10_Vegetables|yam|ଓଲ|जिमीकंद|elephant foot yam
10_Vegetables|taro|ସରୁ|अरबी|taro root
10_Vegetables|ridge gourd|ଝୁଙ୍ଗା|तोरई|ridge gourd
10_Vegetables|snake gourd|ଚିଚିଣ୍ଡା|चिचिंडा|snake gourd
10_Vegetables|drumstick|ସଜନା ଛୁଇଁ|सहजन की फली|drumstick vegetable
10_Vegetables|raw banana|କଞ୍ଚା କଦଳୀ|कच्चा केला|raw banana
10_Vegetables|raw papaya|କଞ୍ଚା ଅମୃତଭଣ୍ଡା|कच्चा पपीता|raw papaya
10_Vegetables|spring onion|ପିଆଜ କଲି|हरा प्याज|spring onion
10_Vegetables|mint|ପୋଦିନା|पुदीना|mint leaves
10_Vegetables|fenugreek|ମେଥି|मेथी|fenugreek leaves
10_Vegetables|mustard greens|ସୋରିଷ ଶାଗ|सरसों का साग|mustard greens
10_Vegetables|cluster beans|ଗୁଆର|ग्वार फली|cluster beans
10_Vegetables|broad beans|ଶିମ୍ବ|सेम|broad beans
10_Vegetables|sweet corn|ମିଠା ମକା|स्वीट कॉर्न|sweet corn
10_Vegetables|zucchini|ଜୁକିନି|ज़ुकीनी|zucchini
10_Vegetables|asparagus|ଆସ୍ପାରାଗସ|शतावरी|asparagus
10_Vegetables|turmeric|ହଳଦୀ|हल्दी|raw turmeric
10_Vegetables|ivy gourd|ତେଲକୁଚା|कुंदरू|ivy gourd
10_Vegetables|banana flower|କଦଳୀ ଫୁଲ|केले का फूल|banana flower
10_Vegetables|soybean|ସୋୟାବିନ|सोयाबीन|soybean
10_Vegetables|red cabbage|ଲାଲ ବନ୍ଧାକୋବି|लाल पत्ता गोभी|red cabbage
10_Vegetables|kohlrabi|ଓଲକୋବି|गाँठ गोभी|kohlrabi
10_Vegetables|leafy greens|ଶାଗ|साग|leafy vegetables
11_Flowers|butterfly pea|ଅପରାଜିତା|अपराजिता|butterfly pea flower
11_Flowers|champak|ଚମ୍ପା|चंपा|champak flower
11_Flowers|dahlia|ଡାହଲିଆ|डहलिया|dahlia flower
11_Flowers|datura|ଧତୁରା|धतूरा|datura flower
11_Flowers|garden daisy|ଡେଜି|डेजी|daisy flower
11_Flowers|gulmohar|କୃଷ୍ଣଚୂଡ଼ା|गुलमोहर|gulmohar flower
11_Flowers|jasmine|ମଲ୍ଲୀ|चमेली|jasmine flower
11_Flowers|lily|ଲିଲି|लिली|lily flower
11_Flowers|lotus|ପଦ୍ମ|कमल|lotus flower
11_Flowers|marigold|ଗେଣ୍ଡୁ|गेंदा|marigold flower
11_Flowers|moonbeam|ଚନ୍ଦ୍ରକାନ୍ତି|चंद्रकांति|moonbeam flower
11_Flowers|rose|ଗୋଲାପ|गुलाब|rose flower
11_Flowers|saffron|କେସରୀ|केसरिया|saffron flower
11_Flowers|sunflower|ସୂର୍ଯ୍ୟମୁଖୀ|सूरजमुखी|sunflower flower
11_Flowers|tuberose|ରଜନୀଗନ୍ଧା|रजनीगंधा|tuberose flower
11_Flowers|water lily|ଶାଳୁକ|कमलिनी|water lily flower
11_Flowers|hibiscus|ମନ୍ଦାର|गुड़हल|hibiscus flower
11_Flowers|tulip|ଟ୍ୟୁଲିପ|ट्यूलिप|tulip flower
11_Flowers|orchid|ଅର୍କିଡ|ऑर्किड|orchid flower
11_Flowers|lavender|ଲ୍ୟାଭେଣ୍ଡର|लैवेंडर|lavender flower
11_Flowers|daffodil|ଡ୍ୟାଫୋଡିଲ|डैफोडिल|daffodil flower
11_Flowers|carnation|କାର୍ନେସନ|कार्नेशन|carnation flower
11_Flowers|chrysanthemum|ଚନ୍ଦ୍ରମଲ୍ଲିକା|गुलदाउदी|chrysanthemum flower
11_Flowers|pansy|ପ୍ୟାନସି|पैंज़ी|pansy flower
11_Flowers|petunia|ପେଟୁନିଆ|पेटुनिया|petunia flower
11_Flowers|zinnia|ଜିନିଆ|जिनिया|zinnia flower
11_Flowers|cosmos|କସମସ|कॉस्मोस|cosmos flower
11_Flowers|poppy|ପପି|पोस्त|poppy flower
11_Flowers|bougainvillea|ବୋଗେନଭିଲା|बोगनवेलिया|bougainvillea flower
11_Flowers|oleander|କରବୀ|कनेर|oleander flower
11_Flowers|night jasmine|ଶେଫାଳି|हरसिंगार|parijat flower
11_Flowers|bakula|ବକୁଳ|मौलसिरी|bakula flower
11_Flowers|kadamba|କଦମ୍ବ|कदंब|kadamba flower
11_Flowers|kewda|କେତକୀ|केवड़ा|kewda flower
11_Flowers|peony|ପିଓନି|पियोनी|peony flower
11_Flowers|iris|ଆଇରିସ|आइरिस|iris flower
11_Flowers|gladiolus|ଗ୍ଲାଡିଓଲସ|ग्लैडियोलस|gladiolus flower
11_Flowers|aster|ଆଷ୍ଟର|एस्टर|aster flower
11_Flowers|hydrangea|ହାଇଡ୍ରାଞ୍ଜିଆ|हाइड्रेंजिया|hydrangea flower
11_Flowers|madhumalati|ମଧୁମାଳତୀ|मधुमालती|madhumalati flower
11_Flowers|tagar|ଟଗର|टगर|tagar flower
11_Flowers|cherry blossom|ଚେରି ବ୍ଲସମ|चेरी ब्लॉसम|cherry blossom flower
11_Flowers|magnolia|ମ୍ୟାଗ୍ନୋଲିଆ|मैगनोलिया|magnolia flower
12_Animals|ant|ପିମ୍ପୁଡ଼ି|चींटी|ant insect
12_Animals|bear|ଭାଲୁ|भालू|bear animal
12_Animals|bee|ମହୁମାଛି|मधुमक्खी|honey bee
12_Animals|buffalo|ମଇଁଷି|भैंस|buffalo
12_Animals|bulbul|ବୁଲବୁଲ|बुलबुल|bulbul bird
12_Animals|bull|ଷଣ୍ଢ|बैल|bull
12_Animals|butterfly|ପ୍ରଜାପତି|तितली|butterfly
12_Animals|cat|ବିଲେଇ|बिल्ली|cat
12_Animals|cobra|ନାଗ|कोबरा|cobra snake
12_Animals|rooster|ଗଞ୍ଜା|मुर्गा|rooster bird
12_Animals|cockroach|ଅସରପା|तिलचट्टा|cockroach
12_Animals|cow|ଗାଈ|गाय|cow
12_Animals|crab|କଙ୍କଡ଼ା|केकड़ा|crab animal
12_Animals|cuckoo|କୋଇଲି|कोयल|cuckoo bird
12_Animals|dog|କୁକୁର|कुत्ता|dog
12_Animals|dolphin|ଡଲଫିନ|डॉल्फिन|dolphin
12_Animals|duck|ବତକ|बत्तख|duck
12_Animals|eagle|ଛଞ୍ଚାଣ|बाज|eagle bird
12_Animals|earthworm|କେଞ୍ଚୁଆ|केंचुआ|earthworm
12_Animals|eel|ବାମ|ईल|eel fish
12_Animals|elephant|ହାତୀ|हाथी|elephant
12_Animals|fox|ଶିଆଳ|लोमड़ी|fox
12_Animals|frog|ବେଙ୍ଗ|मेंढक|frog
12_Animals|swan|ରାଜହଂସ|राजहंस|swan bird
12_Animals|house sparrow|ଚଟିଆ|गौरैया|house sparrow
12_Animals|giraffe|ଜିରାଫ|जिराफ|giraffe
12_Animals|goat|ଛେଳି|बकरी|goat
12_Animals|grasshopper|ଝିଙ୍କା|टिड्डा|grasshopper
12_Animals|goose|ହଂସ|हंस|goose bird
12_Animals|hen|ମାଇକୁକୁଡ଼ା|मुर्गी|hen bird
12_Animals|hippopotamus|ପାଣିହାତୀ|जलहस्ती|hippopotamus
12_Animals|horse|ଘୋଡ଼ା|घोड़ा|horse
12_Animals|jellyfish|ଜେଲିଫିଶ|जेलीफ़िश|jellyfish
12_Animals|kangaroo|କାଙ୍ଗାରୁ|कंगारू|kangaroo
12_Animals|crow|କାଉ|कौआ|crow bird
12_Animals|ladybug|ଲେଡିବଗ|लेडीबग|ladybug
12_Animals|lion|ସିଂହ|शेर|lion
12_Animals|lizard|ଝିଟିପିଟି|छिपकली|lizard
12_Animals|lobster|ଲବଷ୍ଟର|लॉबस्टर|lobster
12_Animals|kingfisher|ମାଛରଙ୍କା|मछरंगा|kingfisher bird
12_Animals|manatee|ମାନାଟି|मैनेटी|manatee
12_Animals|peahen|ମୟୂରୀ|मयूरी|peahen bird
12_Animals|monkey|ମାଙ୍କଡ଼|बंदर|monkey
12_Animals|mosquito|ମଶା|मच्छर|mosquito
12_Animals|octopus|ଅକ୍ଟୋପସ|ऑक्टोपस|octopus
12_Animals|oyster|ଶାମୁକା|सीप|oyster
12_Animals|peacock|ମୟୂର|मोर|peacock
12_Animals|owl|ପେଚା|उल्लू|owl bird
12_Animals|penguin|ପେଙ୍ଗୁଇନ|पेंगुइन|penguin
12_Animals|polar bear|ଧ୍ରୁବୀୟ ଭାଲୁ|ध्रुवीय भालू|polar bear
12_Animals|scorpion|ବିଛା|बिच्छू|scorpion
12_Animals|sea otter|ସମୁଦ୍ର ଓଟର|समुद्री ऊदबिलाव|sea otter
12_Animals|seahorse|ସମୁଦ୍ର ଘୋଡ଼ା|समुद्री घोड़ा|seahorse
12_Animals|seal|ସିଲ|सील|seal animal
12_Animals|shark|ଶାର୍କ|शार्क|shark
12_Animals|sheep|ମେଣ୍ଢା|भेड़|sheep
12_Animals|snake|ସାପ|साँप|snake
12_Animals|spider|ମାକଡ଼ସା|मकड़ी|spider
12_Animals|squid|ସ୍କ୍ୱିଡ|स्क्विड|squid
12_Animals|starfish|ତାରାମାଛ|स्टारफ़िश|starfish
12_Animals|termite|ଉଇ|दीमक|termite insect
12_Animals|tiger|ବାଘ|बाघ|tiger
12_Animals|turtle|କଇଁଛ|कछुआ|turtle
12_Animals|vulture|ଶାଗୁଣା|गिद्ध|vulture bird
12_Animals|whale|ତିମି|व्हेल|whale
12_Animals|wolf|ଗଧିଆ|भेड़िया|wolf
12_Animals|woodpecker|କାଠଠୋକା|कठफोड़वा|woodpecker bird
12_Animals|zebra|ଜେବ୍ରା|ज़ेबरा|zebra
12_Animals|rabbit|ଠେକୁଆ|खरगोश|rabbit
12_Animals|deer|ହରିଣ|हिरण|deer
12_Animals|camel|ଓଟ|ऊँट|camel
12_Animals|donkey|ଗଧ|गधा|donkey
12_Animals|pig|ଘୁଷୁରି|सूअर|pig
12_Animals|rat|ମୂଷା|चूहा|rat animal
12_Animals|squirrel|କାଠବିରାଳି|गिलहरी|squirrel
12_Animals|bat|ବାଦୁଡ଼ି|चमगादड़|bat animal
12_Animals|leopard|ଚିତାବାଘ|तेंदुआ|leopard
12_Animals|cheetah|ଚିତା|चीता|cheetah
12_Animals|rhinoceros|ଗଣ୍ଡା|गैंडा|rhinoceros
12_Animals|panda|ପାଣ୍ଡା|पांडा|panda
12_Animals|koala|କୋଆଲା|कोआला|koala
12_Animals|gorilla|ଗୋରିଲା|गोरिल्ला|gorilla
12_Animals|chimpanzee|ଶିମ୍ପାଞ୍ଜି|चिंपैंज़ी|chimpanzee
12_Animals|crocodile|କୁମ୍ଭୀର|मगरमच्छ|crocodile
12_Animals|hyena|ହାଇନା|लकड़बग्घा|hyena
12_Animals|mongoose|ନକୁଳ|नेवला|mongoose
12_Animals|porcupine|ଶଜାରୁ|साही|porcupine
12_Animals|bison|ବାଇସନ|बाइसन|bison
12_Animals|yak|ୟାକ|याक|yak
12_Animals|llama|ଲାମା|लामा|llama
12_Animals|parrot|ଶୁଆ|तोता|parrot bird
12_Animals|pigeon|ପାରା|कबूतर|pigeon bird
12_Animals|flamingo|ଫ୍ଲେମିଙ୍ଗୋ|फ्लेमिंगो|flamingo
12_Animals|pelican|ପେଲିକାନ|पेलिकन|pelican
12_Animals|sarus crane|ସାରସ|सारस|sarus crane
12_Animals|heron|ବଗ|बगुला|heron bird
12_Animals|myna|ସାରିକା|मैना|myna bird
12_Animals|hornbill|ଧନେଶ|धनेश|hornbill bird
12_Animals|ostrich|ଅଷ୍ଟ୍ରିଚ|शुतुरमुर्ग|ostrich
12_Animals|turkey|ଟର୍କି|टर्की|turkey bird
12_Animals|fly|ମାଛି|मक्खी|housefly
12_Animals|dragonfly|ଫଡ଼ିଙ୍ଗ|ड्रैगनफ्लाई|dragonfly
12_Animals|caterpillar|ଶୁଆପୋକ|इल्ली|caterpillar
12_Animals|snail|ଶମ୍ବୁକ|घोंघा|snail
12_Animals|centipede|ଶତପଦୀ|कनखजूरा|centipede
12_Animals|moth|ପତଙ୍ଗ|पतंगा|moth
12_Animals|chameleon|କୃକଲାସ|गिरगिट|chameleon
12_Animals|python|ଅଜଗର|अजगर|python snake
12_Animals|monitor lizard|ଗୋଧି|गोह|monitor lizard
12_Animals|fish|ମାଛ|मछली|fish
12_Animals|goldfish|ସୁନା ମାଛ|सुनहरी मछली|goldfish
12_Animals|shrimp|ଚିଙ୍ଗୁଡ଼ି|झींगा|shrimp
12_Animals|rohu fish|ରୁହି ମାଛ|रोहू मछली|rohu fish
12_Animals|hilsa|ଇଲିଶି|हिलसा|hilsa fish
12_Animals|olive ridley turtle|ଅଲିଭ ରିଡ଼ଲି କଇଁଛ|ऑलिव रिडले कछुआ|olive ridley turtle
12_Animals|irrawaddy dolphin|ଇରାବତୀ ଡଲଫିନ|इरावदी डॉल्फ़िन|irrawaddy dolphin
12_Animals|calf|ବାଛୁରୀ|बछड़ा|baby cow
12_Animals|puppy|କୁକୁର ଛୁଆ|पिल्ला|puppy
12_Animals|kitten|ବିଲେଇ ଛୁଆ|बिल्ली का बच्चा|kitten
12_Animals|lamb|ମେଣ୍ଢା ଛୁଆ|मेमना|baby sheep
12_Animals|wild boar|ବଣୁଆ ଘୁଷୁରି|जंगली सूअर|wild boar
12_Animals|langur|ହନୁମାନ ବାନର|लंगूर|langur monkey
12_Animals|spotted deer|ଚିତଲ ହରିଣ|चीतल|spotted deer
12_Animals|walrus|ୱାଲରସ|वालरस|walrus
12_Animals|orca|ଓର୍କା|ऑर्का|orca
12_Animals|stingray|ଷ୍ଟିଙ୍ଗରେ|स्टिंग रे|stingray fish
12_Animals|clownfish|କ୍ଲାଉନଫିସ|क्लाउन फिश|clownfish
12_Animals|sea lion|ସି ଲାୟନ|सी लायन|sea lion
13_Body_Parts|arm|ବାହୁ|बाँह|human arm
13_Body_Parts|ear|କାନ|कान|human ear
13_Body_Parts|elbow|କୁହୁଣୀ|कोहनी|human elbow
13_Body_Parts|eye|ଆଖି|आँख|human eye
13_Body_Parts|eyebrow|ଆଖିଭୁଁଇଁ|भौंह|human eyebrow
13_Body_Parts|face|ମୁହଁ|चेहरा|human face
13_Body_Parts|fingers|ଆଙ୍ଗୁଠି|उंगलियाँ|human fingers
13_Body_Parts|foot|ପାଦ|पैर|human foot
13_Body_Parts|hand|ହାତ|हाथ|human hand
13_Body_Parts|head|ମୁଣ୍ଡ|सिर|human head
13_Body_Parts|knee|ଆଣ୍ଠୁ|घुटना|human knee
13_Body_Parts|leg|ଗୋଡ଼|टाँग|human leg
13_Body_Parts|lip|ଓଠ|होंठ|human lip
13_Body_Parts|mouth|ପାଟି|मुँह|human mouth
13_Body_Parts|neck|ବେକ|गर्दन|human neck
13_Body_Parts|nose|ନାକ|नाक|human nose
13_Body_Parts|teeth|ଦାନ୍ତ|दाँत|human teeth
13_Body_Parts|toes|ପାଦ ଆଙ୍ଗୁଠି|पैर की उंगलियाँ|human toes
13_Body_Parts|hair|କେଶ|बाल|human hair
13_Body_Parts|forehead|କପାଳ|माथा|human forehead
13_Body_Parts|cheek|ଗାଲ|गाल|human cheek
13_Body_Parts|chin|ଚିବୁକ|ठोड़ी|human chin
13_Body_Parts|tongue|ଜିଭ|जीभ|human tongue
13_Body_Parts|throat|ଗଳା|गला|human throat
13_Body_Parts|shoulder|କାନ୍ଧ|कंधा|human shoulder
13_Body_Parts|chest|ଛାତି|छाती|human chest
13_Body_Parts|back|ପିଠି|पीठ|human back
13_Body_Parts|stomach|ପେଟ|पेट|human stomach
13_Body_Parts|waist|କଟି|कमर|human waist
13_Body_Parts|thumb|ବୁଢ଼ା ଆଙ୍ଗୁଠି|अंगूठा|human thumb
13_Body_Parts|finger|ଆଙ୍ଗୁଠି|उंगली|human finger
13_Body_Parts|palm|ତଳହାତ|हथेली|human palm
13_Body_Parts|nail|ନଖ|नाखून|human fingernail
13_Body_Parts|wrist|ମଣିବନ୍ଧ|कलाई|human wrist
13_Body_Parts|ankle|ଗୁଲ୍ଫ|टखना|human ankle
13_Body_Parts|heel|ଗୋଇଠି|एड़ी|human heel
13_Body_Parts|thigh|ଜଙ୍ଘ|जाँघ|human thigh
13_Body_Parts|skin|ଚର୍ମ|त्वचा|human skin
13_Body_Parts|heart|ହୃଦୟ|हृदय|human heart
13_Body_Parts|brain|ମସ୍ତିଷ୍କ|दिमाग|human brain
13_Body_Parts|lungs|ଫୁସଫୁସ|फेफड़े|human lungs
13_Body_Parts|bone|ହାଡ଼|हड्डी|human bone
13_Body_Parts|muscle|ମାଂସପେଶୀ|मांसपेशी|human muscle
13_Body_Parts|blood|ରକ୍ତ|खून|blood drop
13_Body_Parts|beard|ଦାଢ଼ି|दाढ़ी|human beard
13_Body_Parts|moustache|ଗୁମ୍ଫ|मूँछ|human moustache
13_Body_Parts|liver|ଯକୃତ|जिगर|human liver
13_Body_Parts|kidney|ବୃକ୍କ|गुर्दा|human kidney
13_Body_Parts|ribs|ପଞ୍ଜରା|पसलियाँ|human ribs
13_Body_Parts|navel|ନାଭି|नाभि|human navel
13_Body_Parts|jaw|ହନୁ|जबड़ा|human jaw
13_Body_Parts|eyelid|ଆଖିପତା|पलक|human eyelid
13_Body_Parts|nostril|ନାକ ଛିଦ୍ର|नथुना|human nostril
13_Body_Parts|fist|ମୁଠା|मुट्ठी|human fist
13_Body_Parts|armpit|କାଖ|बगल|human armpit
13_Body_Parts|spine|ମେରୁଦଣ୍ଡ|रीढ़ की हड्डी|human spine
14_Emotions|angry|ରାଗ|गुस्सा|angry child
14_Emotions|cry|କାନ୍ଦିବା|रोना|crying child
14_Emotions|excited|ଉତ୍ସାହିତ|उत्साहित|excited child
14_Emotions|happy|ଖୁସି|खुश|happy child
14_Emotions|proud|ଗର୍ବିତ|गर्वित|proud child
14_Emotions|sad|ଦୁଃଖୀ|उदास|sad child
14_Emotions|scared|ଡରିବା|डरा हुआ|scared child
14_Emotions|shy|ଲାଜ|शर्मीला|shy child
14_Emotions|sleepy|ନିଦ୍ରାଳୁ|नींद आना|sleepy child
14_Emotions|surprised|ଆଶ୍ଚର୍ଯ୍ୟ|आश्चर्यचकित|surprised child
14_Emotions|love|ପ୍ରେମ|प्यार|child hug
14_Emotions|laughing|ହସିବା|हँसना|laughing child
14_Emotions|smiling|ମୁରୁକି ହସ|मुस्कुराना|smiling child
14_Emotions|worried|ଚିନ୍ତିତ|चिंतित|worried child
14_Emotions|tired|କ୍ଳାନ୍ତ|थका हुआ|tired child
14_Emotions|hungry|ଭୋକିଲା|भूखा|hungry child
14_Emotions|thirsty|ଶୋଷିଲା|प्यासा|thirsty child
14_Emotions|bored|ବିରକ୍ତ|ऊबा हुआ|bored child
14_Emotions|confused|ଦ୍ୱନ୍ଦ୍ୱରେ|उलझन में|confused child
14_Emotions|lonely|ଏକୁଟିଆ|अकेला|lonely child
14_Emotions|jealous|ଈର୍ଷାଳୁ|ईर्ष्यालु|jealous child
14_Emotions|nervous|ଘାବରା|घबराया हुआ|nervous child
14_Emotions|brave|ସାହସୀ|बहादुर|brave child
14_Emotions|kind|ଦୟାଳୁ|दयालु|kind child
14_Emotions|calm|ଶାନ୍ତ|शांत|calm child
14_Emotions|sick|ଅସୁସ୍ଥ|बीमार|sick child
14_Emotions|ashamed|ଲଜ୍ଜିତ|शर्मिंदा|ashamed child
14_Emotions|disgusted|ଘୃଣା|घृणा|disgusted child
14_Emotions|grateful|କୃତଜ୍ଞ|आभारी|grateful child
14_Emotions|curious|କୌତୂହଳୀ|जिज्ञासु|curious child
14_Emotions|hopeful|ଆଶାବାଦୀ|आशावान|hopeful child
14_Emotions|cheerful|ଉଲ୍ଲସିତ|प्रसन्न|cheerful child
14_Emotions|silly|ମଜାଳିଆ|मज़ाकिया|silly child
14_Emotions|sleeping|ଶୋଇବା|सोना|sleeping child
14_Emotions|determined|ଦୃଢ଼ ସଂକଳ୍ପ|दृढ़ निश्चयी|determined child
15_Household|air conditioner|ଏସି|एयर कंडीशनर|air conditioner
15_Household|bed|ଶଯ୍ୟା|बिस्तर|bed
15_Household|blender|ବ୍ଲେଣ୍ଡର|ब्लेंडर|blender
15_Household|ceiling fan|ଛାତ ପଙ୍ଖା|सीलिंग फैन|ceiling fan
15_Household|pressure cooker|କୁକର|प्रेशर कुकर|pressure cooker
15_Household|dishwasher|ଡିସୱାସର|डिशवॉशर|dishwasher
15_Household|dustbin|ଆବର୍ଜନା ଡବା|कूड़ादान|dustbin
15_Household|gas stove|ଗ୍ୟାସ ଚୁଲା|गैस चूल्हा|gas stove
15_Household|iron|ଇସ୍ତିରି|इस्तरी|clothes iron
15_Household|oven|ଓଭେନ|ओवन|oven
15_Household|refrigerator|ଫ୍ରିଜ|फ्रिज|refrigerator
15_Household|sewing machine|ସିଲେଇ ମେସିନ|सिलाई मशीन|sewing machine
15_Household|television|ଟେଲିଭିଜନ|टेलीविजन|television
15_Household|toaster|ଟୋଷ୍ଟର|टोस्टर|toaster
15_Household|vacuum cleaner|ଭ୍ୟାକ୍ୟୁମ କ୍ଲିନର|वैक्यूम क्लीनर|vacuum cleaner
15_Household|washing machine|ଧୋଇବା ମେସିନ|वाशिंग मशीन|washing machine
15_Household|water purifier|ପାଣି ଫିଲ୍ଟର|वॉटर प्यूरीफायर|water purifier
15_Household|water heater|ପାଣି ଗରମ କରିବା|वॉटर हीटर|water heater
15_Household|table|ଟେବୁଲ|मेज़|wooden table
15_Household|chair|ଚଉକି|कुर्सी|chair
15_Household|sofa|ସୋଫା|सोफ़ा|sofa
15_Household|almirah|ଆଲମିରା|अलमारी|almirah
15_Household|mirror|ଦର୍ପଣ|आईना|mirror
15_Household|wall clock|କାନ୍ଥ ଘଡ଼ି|दीवार घड़ी|wall clock
15_Household|light bulb|ବଲ୍ବ|बल्ब|light bulb
15_Household|door|ଦ୍ୱାର|दरवाज़ा|door
15_Household|window|ଝରକା|खिड़की|window
15_Household|broom|ଝାଡ଼ୁ|झाड़ू|broom
15_Household|bucket|ବାଲଟି|बाल्टी|bucket
15_Household|mug|ମଗ|मग|mug
15_Household|plate|ଥାଳି|थाली|plate
15_Household|spoon|ଚାମଚ|चम्मच|spoon
15_Household|glass|ଗ୍ଲାସ|गिलास|drinking glass
15_Household|cup|କପ|कप|cup
15_Household|bowl|ବାଟି|कटोरी|bowl
15_Household|knife|ଛୁରୀ|चाकू|kitchen knife
15_Household|fork|କଣ୍ଟା|काँटा|dinner fork
15_Household|pot|ହାଣ୍ଡି|हाँडी|cooking pot
15_Household|frying pan|କଡ଼ାଇ|कड़ाही|frying pan
15_Household|kettle|କେଟଲି|केतली|kettle
15_Household|pillow|ବାଲିସ|तकिया|pillow
15_Household|blanket|କମ୍ବଳ|कंबल|blanket
15_Household|mat|ମାଦୁର|चटाई|floor mat
15_Household|curtain|ପରଦା|पर्दा|curtain
15_Household|telephone|ଟେଲିଫୋନ|टेलीफोन|landline telephone
15_Household|mobile phone|ମୋବାଇଲ|मोबाइल|mobile phone
15_Household|torch|ଟର୍ଚ୍ଚ|टॉर्च|flashlight
15_Household|umbrella|ଛତା|छाता|umbrella
15_Household|lock|ତାଲା|ताला|padlock
15_Household|key|ଚାବି|चाबी|door key
15_Household|soap|ସାବୁନ|साबुन|soap bar
15_Household|towel|ତଉଲିଆ|तौलिया|towel
15_Household|comb|କଂଘେଇ|कंघी|comb
15_Household|toothbrush|ଦାନ୍ତ ବ୍ରଶ|टूथब्रश|toothbrush
15_Household|scissors|କଞ୍ଚି|कैंची|scissors
15_Household|hammer|ହାତୁଡ଼ି|हथौड़ा|hammer
15_Household|ladder|ସିଢ଼ି|सीढ़ी|ladder
15_Household|tap|ନଳ|नल|water tap
15_Household|table fan|ଟେବୁଲ ପଙ୍ଖା|टेबल फैन|table fan
15_Household|lantern|ଲଣ୍ଠନ|लालटेन|lantern
15_Household|candle|ମହମବତୀ|मोमबत्ती|candle
15_Household|matchbox|ଦିଆସିଲି|माचिस|matchbox
15_Household|mixer grinder|ମିକ୍ସର|मिक्सर ग्राइंडर|mixer grinder
15_Household|grinding stone|ଶିଲପୁଆ|सिलबट्टा|sil batta
15_Household|bookshelf|ବହି ଆଲମାରୀ|किताबों की अलमारी|bookshelf
15_Household|hanger|ହ୍ୟାଙ୍ଗର|हैंगर|clothes hanger
15_Household|inverter|ଇନଭର୍ଟର|इन्वर्टर|home inverter
15_Household|switch board|ସ୍ୱିଚ ବୋର୍ଡ|स्विच बोर्ड|switch board
15_Household|cot|ଖଟ|खाट|cot bed
15_Household|stool|ଷ୍ଟୁଲ|स्टूल|stool
15_Household|diya lamp|ଦୀପ|दीया|diya
15_Household|photo frame|ଫଟୋ ଫ୍ରେମ|फोटो फ्रेम|photo frame
15_Household|flower vase|ଫୁଲଦାନୀ|फूलदान|flower vase
15_Household|dining table|ଖାଇବା ଟେବୁଲ|खाने की मेज़|dining table
16_Transport|aeroplane|ବିମାନ|हवाई जहाज|aeroplane
16_Transport|ambulance|ଆମ୍ବୁଲାନ୍ସ|एम्बुलेंस|ambulance
16_Transport|auto rickshaw|ଅଟୋ|ऑटो रिक्शा|auto rickshaw
16_Transport|bicycle|ସାଇକେଲ|साइकिल|bicycle
16_Transport|bullock cart|ବଳଦ ଗାଡ଼ି|बैलगाड़ी|bullock cart
16_Transport|bus|ବସ|बस|bus
16_Transport|car|କାର|कार|car
16_Transport|fighter plane|ଯୁଦ୍ଧ ବିମାନ|लड़ाकू विमान|fighter jet
16_Transport|helicopter|ହେଲିକପ୍ଟର|हेलीकॉप्टर|helicopter
16_Transport|JCB|ଜେସିବି|जेसीबी|JCB
16_Transport|jeep|ଜିପ|जीप|jeep
16_Transport|rocket|ରକେଟ|रॉकेट|rocket launch
16_Transport|scooter|ସ୍କୁଟର|स्कूटर|scooter
16_Transport|ship|ଜାହାଜ|जहाज|ship
16_Transport|space shuttle|ସ୍ପେସ ସଟଲ|स्पेस शटल|space shuttle
16_Transport|submarine|ଜଳଯାନ|पनडुब्बी|submarine
16_Transport|tank|ଟ୍ୟାଙ୍କ|टैंक|army tank
16_Transport|tractor|ଟ୍ରାକ୍ଟର|ट्रैक्टर|tractor
16_Transport|train|ଟ୍ରେନ|रेलगाड़ी|train
16_Transport|truck|ଟ୍ରକ|ट्रक|truck
16_Transport|water scooter|ୱାଟର ସ୍କୁଟର|वॉटर स्कूटर|jet ski
16_Transport|motorcycle|ମୋଟରସାଇକେଲ|मोटरसाइकिल|motorcycle
16_Transport|cycle rickshaw|ସାଇକେଲ ରିକ୍ସା|साइकिल रिक्शा|cycle rickshaw
16_Transport|taxi|ଟ୍ୟାକ୍ସି|टैक्सी|taxi
16_Transport|van|ଭ୍ୟାନ|वैन|van vehicle
16_Transport|metro train|ମେଟ୍ରୋ ଟ୍ରେନ|मेट्रो ट्रेन|metro train
16_Transport|boat|ଡଙ୍ଗା|नाव|boat
16_Transport|cruise ship|କ୍ରୁଜ ଜାହାଜ|क्रूज़ जहाज़|cruise ship
16_Transport|tram|ଟ୍ରାମ|ट्राम|tram
16_Transport|fire engine|ଅଗ୍ନିଶମ ଗାଡ଼ି|दमकल गाड़ी|fire engine
16_Transport|police car|ପୋଲିସ ଗାଡ଼ି|पुलिस की गाड़ी|police car
16_Transport|school bus|ସ୍କୁଲ ବସ|स्कूल बस|school bus
16_Transport|horse cart|ଘୋଡ଼ା ଗାଡ଼ି|तांगा|horse cart
16_Transport|hot air balloon|ଗରମ ବାୟୁ ବେଲୁନ|गर्म हवा का गुब्बारा|hot air balloon
16_Transport|cable car|କେବୁଲ କାର|केबल कार|cable car
16_Transport|bullet train|ବୁଲେଟ ଟ୍ରେନ|बुलेट ट्रेन|bullet train
16_Transport|crane|କ୍ରେନ|क्रेन|construction crane
16_Transport|bulldozer|ବୁଲଡୋଜର|बुलडोज़र|bulldozer
16_Transport|road roller|ରୋଡ ରୋଲର|रोड रोलर|road roller
16_Transport|dump truck|ଡମ୍ପର ଟ୍ରକ|डंपर ट्रक|dump truck
16_Transport|ferry|ଫେରି|फेरी|ferry boat
16_Transport|speed boat|ସ୍ପିଡବୋଟ|स्पीडबोट|speed boat
16_Transport|sailing boat|ପାଲ ଡଙ୍ଗା|पाल वाली नाव|sailing boat
16_Transport|jet plane|ଜେଟ ବିମାନ|जेट विमान|passenger jet
16_Transport|wheelchair|ହ୍ୱିଲଚେୟାର|व्हीलचेयर|wheelchair
16_Transport|handcart|ଠେଲା ଗାଡ଼ି|ठेला|handcart
16_Transport|tanker truck|ଟ୍ୟାଙ୍କର|टैंकर|tanker truck
16_Transport|electric car|ଇଲେକ୍ଟ୍ରିକ କାର|इलेक्ट्रिक कार|electric car
16_Transport|e-rickshaw|ଇ-ରିକ୍ସା|ई-रिक्शा|e-rickshaw
16_Transport|steam engine|ବାଷ୍ପ ଇଞ୍ଜିନ|भाप इंजन|steam locomotive
16_Transport|tempo|ଟେମ୍ପୋ|टेम्पो|tempo vehicle
16_Transport|kayak|କାୟାକ|कयाक|kayak
16_Transport|lifeboat|ଜୀବନ ରକ୍ଷା ଡଙ୍ଗା|लाइफबोट|lifeboat
17_Professions|barber|ନାଇ|नाई|barber
17_Professions|builder|ନିର୍ମାତା|बिल्डर|construction worker
17_Professions|doctor|ଡାକ୍ତର|डॉक्टर|doctor
17_Professions|electrician|ବିଦ୍ୟୁତ କାରିଗର|इलेक्ट्रीशियन|electrician
17_Professions|farmer|ଚାଷୀ|किसान|farmer
17_Professions|magician|ଯାଦୁଗର|जादूगर|magician
17_Professions|nurse|ନର୍ସ|नर्स|nurse
17_Professions|painter|ଚିତ୍ରକର|पेंटर|house painter
17_Professions|photographer|ଫଟୋଗ୍ରାଫର|फोटोग्राफर|photographer
17_Professions|pilot|ପାଇଲଟ|पायलट|pilot
17_Professions|police|ପୋଲିସ|पुलिस|police officer
17_Professions|postman|ଡାକିଆ|पोस्टमैन|postman
17_Professions|potter|କୁମ୍ଭାର|कुम्हार|potter
17_Professions|scientist|ବୈଜ୍ଞାନିକ|वैज्ञानिक|scientist
17_Professions|singer|ଗାୟକ|गायक|singer
17_Professions|soldier|ସୈନିକ|सैनिक|soldier
17_Professions|tailor|ଦରଜି|दर्जी|tailor
17_Professions|teacher|ଶିକ୍ଷକ|शिक्षक|teacher
17_Professions|waiter|ୱେଟର|वेटर|waiter
17_Professions|engineer|ଇଞ୍ଜିନିୟର|इंजीनियर|engineer
17_Professions|lawyer|ଓକିଲ|वकील|lawyer
17_Professions|judge|ବିଚାରପତି|न्यायाधीश|judge
17_Professions|driver|ଡ୍ରାଇଭର|ड्राइवर|car driver
17_Professions|cook|ରୋଷେୟା|रसोइया|cook
17_Professions|baker|ବେକର|बेकर|baker
17_Professions|fisherman|ମାଛୁଆ|मछुआरा|fisherman
17_Professions|carpenter|ବଢ଼େଇ|बढ़ई|carpenter
17_Professions|blacksmith|କମାର|लोहार|blacksmith
17_Professions|goldsmith|ସୁନାର|सुनार|goldsmith
17_Professions|mason|ରାଜମିସ୍ତ୍ରୀ|राजमिस्त्री|mason
17_Professions|plumber|ପ୍ଲମ୍ବର|प्लंबर|plumber
17_Professions|mechanic|ମେକାନିକ|मैकेनिक|mechanic
17_Professions|shopkeeper|ଦୋକାନୀ|दुकानदार|shopkeeper
17_Professions|vegetable seller|ପରିବା ବିକ୍ରେତା|सब्ज़ीवाला|vegetable seller
17_Professions|milkman|ଦୁଧ ବିକ୍ରେତା|दूधवाला|milkman
17_Professions|cobbler|ମୋଚି|मोची|cobbler
17_Professions|weaver|ତନ୍ତୀ|बुनकर|weaver
17_Professions|washerman|ଧୋବା|धोबी|dhobi
17_Professions|gardener|ମାଳୀ|माली|gardener
17_Professions|firefighter|ଅଗ୍ନିଶମ କର୍ମୀ|दमकलकर्मी|firefighter
17_Professions|astronaut|ମହାକାଶଚାରୀ|अंतरिक्ष यात्री|astronaut
17_Professions|dentist|ଦନ୍ତ ଚିକିତ୍ସକ|दंत चिकित्सक|dentist
17_Professions|veterinarian|ପଶୁ ଚିକିତ୍ସକ|पशु चिकित्सक|veterinarian
17_Professions|journalist|ସାମ୍ବାଦିକ|पत्रकार|journalist
17_Professions|artist|କଳାକାର|कलाकार|artist
17_Professions|dancer|ନର୍ତ୍ତକ|नर्तक|dancer
17_Professions|musician|ସଙ୍ଗୀତଜ୍ଞ|संगीतकार|musician
17_Professions|actor|ଅଭିନେତା|अभिनेता|actor
17_Professions|sportsman|ଖେଳାଳି|खिलाड़ी|athlete
17_Professions|bank clerk|ବ୍ୟାଙ୍କ କର୍ମଚାରୀ|बैंक कर्मचारी|bank clerk
17_Professions|security guard|ପ୍ରହରୀ|चौकीदार|security guard
17_Professions|shepherd|ମେଷପାଳକ|चरवाहा|shepherd
17_Professions|priest|ପୂଜାରୀ|पुजारी|hindu priest
17_Professions|professor|ପ୍ରାଧ୍ୟାପକ|प्रोफेसर|professor
17_Professions|pharmacist|ଔଷଧ ବିକ୍ରେତା|दवा विक्रेता|pharmacist
17_Professions|architect|ସ୍ଥପତି|वास्तुकार|architect
17_Professions|writer|ଲେଖକ|लेखक|writer
17_Professions|bus conductor|କଣ୍ଡକ୍ଟର|कंडक्टर|bus conductor
17_Professions|chef|ଶେଫ|शेफ|chef
17_Professions|cleaner|ସଫେଇ କର୍ମୀ|सफाईकर्मी|street sweeper
17_Professions|coach|ପ୍ରଶିକ୍ଷକ|प्रशिक्षक|sports coach
17_Professions|cameraman|କ୍ୟାମେରାମ୍ୟାନ|कैमरामैन|cameraman
17_Professions|tea seller|ଚା ବିକ୍ରେତା|चायवाला|tea seller
17_Professions|ice cream seller|ଆଇସକ୍ରିମ ବିକ୍ରେତା|आइसक्रीम वाला|ice cream seller
25_Computers|CPU|ସିପିୟୁ|सीपीयू|cpu cabinet
25_Computers|headphone|ହେଡଫୋନ|हेडफोन|headphones
25_Computers|keyboard|କିବୋର୍ଡ|कीबोर्ड|keyboard
25_Computers|monitor|ମନିଟର|मॉनिटर|computer monitor
25_Computers|mouse|ମାଉସ|माउस|computer mouse
25_Computers|pen drive|ପେନ ଡ୍ରାଇଭ|पेन ड्राइव|pen drive
25_Computers|printer|ପ୍ରିଣ୍ଟର|प्रिंटर|printer
25_Computers|scanner|ସ୍କାନର|स्कैनर|document scanner
25_Computers|speakers|ସ୍ପିକର|स्पीकर|computer speakers
25_Computers|UPS|ୟୁପିଏସ|यूपीएस|computer UPS
25_Computers|web camera|ୱେବ କ୍ୟାମେରା|वेब कैमरा|webcam
25_Computers|laptop|ଲାପଟପ|लैपटॉप|laptop
25_Computers|desktop computer|ଡେସ୍କଟପ କମ୍ପ୍ୟୁଟର|डेस्कटॉप कंप्यूटर|desktop computer
25_Computers|tablet|ଟାବଲେଟ|टैबलेट|tablet
25_Computers|smartphone|ସ୍ମାର୍ଟଫୋନ|स्मार्टफोन|smartphone
25_Computers|microphone|ମାଇକ୍ରୋଫୋନ|माइक्रोफोन|microphone
25_Computers|router|ରାଉଟର|राउटर|wifi router
25_Computers|modem|ମଡେମ|मॉडेम|modem
25_Computers|hard disk|ହାର୍ଡ ଡିସ୍କ|हार्ड डिस्क|hard disk
25_Computers|CD|ସିଡି|सीडी|CD disc
25_Computers|memory card|ମେମୋରୀ କାର୍ଡ|मेमोरी कार्ड|memory card
25_Computers|projector|ପ୍ରୋଜେକ୍ଟର|प्रोजेक्टर|projector
25_Computers|joystick|ଜୟଷ୍ଟିକ|जॉयस्टिक|joystick
25_Computers|mouse pad|ମାଉସ ପ୍ୟାଡ|माउस पैड|mouse pad
25_Computers|USB cable|ୟୁଏସବି କେବୁଲ|यूएसबी केबल|USB cable
25_Computers|charger|ଚାର୍ଜର|चार्जर|mobile charger
25_Computers|power bank|ପାୱାର ବ୍ୟାଙ୍କ|पावर बैंक|power bank
25_Computers|motherboard|ମଦରବୋର୍ଡ|मदरबोर्ड|motherboard
25_Computers|RAM|ରାମ|रैम|RAM stick
25_Computers|smart watch|ସ୍ମାର୍ଟ ୱାଚ|स्मार्ट वॉच|smart watch
25_Computers|game controller|ଗେମ କଣ୍ଟ୍ରୋଲର|गेम कंट्रोलर|game controller
25_Computers|WiFi|ୱାଇ-ଫାଇ|वाई-फाई|wifi symbol
25_Computers|robot|ରୋବଟ|रोबोट|robot
25_Computers|drone|ଡ୍ରୋନ|ड्रोन|drone
26_Festivals|Buddha Purnima|ବୁଦ୍ଧ ପୂର୍ଣ୍ଣିମା|बुद्ध पूर्णिमा|Buddha Purnima
26_Festivals|Dasahera|ଦଶହରା|दशहरा|Dussehra
26_Festivals|Diwali|ଦୀପାବଳି|दिवाली|Diwali
26_Festivals|Eid|ଈଦ|ईद|Eid
26_Festivals|Holi|ହୋଲି|होली|Holi
26_Festivals|Independence Day|ସ୍ୱାଧୀନତା ଦିବସ|स्वतंत्रता दिवस|India Independence Day
26_Festivals|Janmashtami|ଜନ୍ମାଷ୍ଟମୀ|जन्माष्टमी|Janmashtami
26_Festivals|Kartika Purnima|କାର୍ତ୍ତିକ ପୂର୍ଣ୍ଣିମା|कार्तिक पूर्णिमा|Boita Bandana
26_Festivals|Kumara Purnima|କୁମାର ପୂର୍ଣ୍ଣିମା|कुमार पूर्णिमा|Kumar Purnima
26_Festivals|Nuakhai|ନୂଆଖାଇ|नुआखाई|Nuakhai
26_Festivals|Raksha Bandhan|ରକ୍ଷାବନ୍ଧନ|रक्षाबंधन|Raksha Bandhan
26_Festivals|Rath Yatra|ରଥଯାତ୍ରା|रथ यात्रा|Rath Yatra Puri
26_Festivals|Republic Day|ଗଣତନ୍ତ୍ର ଦିବସ|गणतंत्र दिवस|Republic Day parade
26_Festivals|Shivaratri|ଶିବରାତ୍ରି|शिवरात्रि|Maha Shivaratri
26_Festivals|Christmas|କ୍ରିସମସ|क्रिसमस|Christmas
26_Festivals|Durga Puja|ଦୁର୍ଗା ପୂଜା|दुर्गा पूजा|Durga Puja
26_Festivals|Kali Puja|କାଳୀ ପୂଜା|काली पूजा|Kali Puja
26_Festivals|Ganesh Chaturthi|ଗଣେଶ ଚତୁର୍ଥୀ|गणेश चतुर्थी|Ganesh Chaturthi
26_Festivals|Saraswati Puja|ସରସ୍ୱତୀ ପୂଜା|सरस्वती पूजा|Saraswati Puja
26_Festivals|Laxmi Puja|ଲକ୍ଷ୍ମୀ ପୂଜା|लक्ष्मी पूजा|Laxmi Puja
26_Festivals|Makar Sankranti|ମକର ସଂକ୍ରାନ୍ତି|मकर संक्रांति|Makar Sankranti
26_Festivals|Pongal|ପୋଙ୍ଗଲ|पोंगल|Pongal
26_Festivals|Onam|ଓଣମ|ओणम|Onam
26_Festivals|Navratri|ନବରାତ୍ରି|नवरात्रि|Navratri
26_Festivals|Ram Navami|ରାମ ନବମୀ|राम नवमी|Ram Navami
26_Festivals|Hanuman Jayanti|ହନୁମାନ ଜୟନ୍ତୀ|हनुमान जयंती|Hanuman Jayanti
26_Festivals|Baisakhi|ବୈଶାଖୀ|बैसाखी|Baisakhi
26_Festivals|Lohri|ଲୋହରି|लोहड़ी|Lohri
26_Festivals|Gandhi Jayanti|ଗାନ୍ଧୀ ଜୟନ୍ତୀ|गांधी जयंती|Gandhi Jayanti
26_Festivals|Teachers Day|ଶିକ୍ଷକ ଦିବସ|शिक्षक दिवस|Teachers Day India
26_Festivals|Childrens Day|ଶିଶୁ ଦିବସ|बाल दिवस|Childrens Day India
26_Festivals|New Year|ନୂଆ ବର୍ଷ|नया साल|New Year fireworks
26_Festivals|Good Friday|ଗୁଡ ଫ୍ରାଇଡେ|गुड फ्राइडे|Good Friday
26_Festivals|Easter|ଇଷ୍ଟର|ईस्टर|Easter eggs
26_Festivals|Mahavir Jayanti|ମହାବୀର ଜୟନ୍ତୀ|महावीर जयंती|Mahavir Jayanti
26_Festivals|Guru Nanak Jayanti|ଗୁରୁନାନକ ଜୟନ୍ତୀ|गुरु नानक जयंती|Guru Nanak Jayanti
26_Festivals|Chhath Puja|ଛଠ ପୂଜା|छठ पूजा|Chhath Puja
26_Festivals|Bali Yatra|ବାଲି ଯାତ୍ରା|बाली यात्रा|Bali Yatra
26_Festivals|Raja Parba|ରଜ ପର୍ବ|रज पर्व|Raja Parba
26_Festivals|Chandan Yatra|ଚନ୍ଦନ ଯାତ୍ରା|चंदन यात्रा|Chandan Yatra
26_Festivals|Dola Purnima|ଦୋଳ ପୂର୍ଣ୍ଣିମା|दोल पूर्णिमा|Dola Purnima
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
27_Currency|piggy bank|ଗୋଲକ|गुल्लक|piggy bank
27_Currency|wallet|ପର୍ସ|बटुआ|wallet
27_Currency|ATM card|ଏଟିଏମ କାର୍ଡ|एटीएम कार्ड|ATM card
27_Currency|cheque|ଚେକ|चेक|bank cheque
27_Currency|passbook|ପାସବୁକ|पासबुक|bank passbook
27_Currency|bank|ବ୍ୟାଙ୍କ|बैंक|bank building
27_Currency|ATM machine|ଏଟିଏମ ମେସିନ|एटीएम मशीन|ATM machine
27_Currency|dollar note|ଡଲାର ନୋଟ|डॉलर नोट|US dollar bill
27_Currency|coins|ମୁଦ୍ରା|सिक्के|indian coins
27_Currency|gold coin|ସୁନା ମୁଦ୍ରା|सोने का सिक्का|gold coin
27_Currency|QR code payment|କ୍ୟୁଆର କୋଡ ପେମେଣ୍ଟ|क्यूआर कोड भुगतान|UPI QR code
28_Countries|Afghanistan|ଆଫଗାନିସ୍ତାନ|अफ़ग़ानिस्तान|Afghanistan flag
28_Countries|Australia|ଅଷ୍ଟ୍ରେଲିଆ|ऑस्ट्रेलिया|Australia flag
28_Countries|Bangladesh|ବାଂଲାଦେଶ|बांग्लादेश|Bangladesh flag
28_Countries|Bhutan|ଭୁଟାନ|भूटान|Bhutan flag
28_Countries|Brazil|ବ୍ରାଜିଲ|ब्राज़ील|Brazil flag
28_Countries|Canada|କାନାଡା|कनाडा|Canada flag
28_Countries|China|ଚୀନ|चीन|China flag
28_Countries|France|ଫ୍ରାନ୍ସ|फ़्रांस|France flag
28_Countries|Germany|ଜର୍ମାନୀ|जर्मनी|Germany flag
28_Countries|India|ଭାରତ|भारत|India flag
28_Countries|Iran|ଇରାନ|ईरान|Iran flag
28_Countries|Italy|ଇଟାଲୀ|इटली|Italy flag
28_Countries|Kenya|କେନିଆ|केन्या|Kenya flag
28_Countries|Malaysia|ମାଲେସିଆ|मलेशिया|Malaysia flag
28_Countries|Myanmar|ମିଆଁମାର|म्यांमार|Myanmar flag
28_Countries|Nepal|ନେପାଳ|नेपाल|Nepal flag
28_Countries|Pakistan|ପାକିସ୍ତାନ|पाकिस्तान|Pakistan flag
28_Countries|Russia|ରୁଷିଆ|रूस|Russia flag
28_Countries|South Africa|ଦକ୍ଷିଣ ଆଫ୍ରିକା|दक्षिण अफ्रीका|South Africa flag
28_Countries|Sri Lanka|ଶ୍ରୀଲଙ୍କା|श्रीलंका|Sri Lanka flag
28_Countries|Turkey|ତୁର୍କୀ|तुर्की|Turkey flag
28_Countries|USA|ଆମେରିକା|अमेरिका|USA flag
28_Countries|Japan|ଜାପାନ|जापान|Japan flag
28_Countries|South Korea|ଦକ୍ଷିଣ କୋରିଆ|दक्षिण कोरिया|South Korea flag
28_Countries|Indonesia|ଇଣ୍ଡୋନେସିଆ|इंडोनेशिया|Indonesia flag
28_Countries|Thailand|ଥାଇଲାଣ୍ଡ|थाईलैंड|Thailand flag
28_Countries|Vietnam|ଭିଏତନାମ|वियतनाम|Vietnam flag
28_Countries|Singapore|ସିଙ୍ଗାପୁର|सिंगापुर|Singapore flag
28_Countries|Philippines|ଫିଲିପାଇନ୍ସ|फिलीपींस|Philippines flag
28_Countries|Maldives|ମାଲଦ୍ୱୀପ|मालदीव|Maldives flag
28_Countries|Saudi Arabia|ସାଉଦି ଆରବ|सऊदी अरब|Saudi Arabia flag
28_Countries|UAE|ସଂଯୁକ୍ତ ଆରବ ଏମିରେଟ୍ସ|संयुक्त अरब अमीरात|UAE flag
28_Countries|Iraq|ଇରାକ|इराक|Iraq flag
28_Countries|Israel|ଇସ୍ରାଏଲ|इज़राइल|Israel flag
28_Countries|Egypt|ମିଶର|मिस्र|Egypt flag
28_Countries|Nigeria|ନାଇଜେରିଆ|नाइजीरिया|Nigeria flag
28_Countries|Ethiopia|ଇଥିଓପିଆ|इथियोपिया|Ethiopia flag
28_Countries|Ghana|ଘାନା|घाना|Ghana flag
28_Countries|Morocco|ମୋରୋକ୍କୋ|मोरक्को|Morocco flag
28_Countries|United Kingdom|ଯୁକ୍ତରାଜ୍ୟ|यूनाइटेड किंगडम|United Kingdom flag
28_Countries|Ireland|ଆୟର୍ଲ୍ୟାଣ୍ଡ|आयरलैंड|Ireland flag
28_Countries|Spain|ସ୍ପେନ|स्पेन|Spain flag
28_Countries|Portugal|ପର୍ତ୍ତୁଗାଲ|पुर्तगाल|Portugal flag
28_Countries|Netherlands|ନେଦରଲ୍ୟାଣ୍ଡ|नीदरलैंड|Netherlands flag
28_Countries|Switzerland|ସ୍ୱିଜରଲ୍ୟାଣ୍ଡ|स्विट्ज़रलैंड|Switzerland flag
28_Countries|Sweden|ସ୍ୱିଡେନ|स्वीडन|Sweden flag
28_Countries|Norway|ନରୱେ|नॉर्वे|Norway flag
28_Countries|Denmark|ଡେନମାର୍କ|डेनमार्क|Denmark flag
28_Countries|Finland|ଫିନଲ୍ୟାଣ୍ଡ|फ़िनलैंड|Finland flag
28_Countries|Greece|ଗ୍ରୀସ|यूनान|Greece flag
28_Countries|Poland|ପୋଲାଣ୍ଡ|पोलैंड|Poland flag
28_Countries|Ukraine|ୟୁକ୍ରେନ|यूक्रेन|Ukraine flag
28_Countries|Mexico|ମେକ୍ସିକୋ|मेक्सिको|Mexico flag
28_Countries|Argentina|ଆର୍ଜେଣ୍ଟିନା|अर्जेंटीना|Argentina flag
28_Countries|Cuba|କ୍ୟୁବା|क्यूबा|Cuba flag
28_Countries|Peru|ପେରୁ|पेरू|Peru flag
28_Countries|Chile|ଚିଲି|चिली|Chile flag
28_Countries|New Zealand|ନିଉଜିଲ୍ୟାଣ୍ଡ|न्यूज़ीलैंड|New Zealand flag
28_Countries|Mongolia|ମଙ୍ଗୋଲିଆ|मंगोलिया|Mongolia flag
28_Countries|Kazakhstan|କାଜାକସ୍ତାନ|कज़ाखस्तान|Kazakhstan flag
28_Countries|Tanzania|ତାନଜାନିଆ|तंज़ानिया|Tanzania flag
28_Countries|Kuwait|କୁଏତ|कुवैत|Kuwait flag
28_Countries|Qatar|କତାର|क़तर|Qatar flag
28_Countries|Oman|ଓମାନ|ओमान|Oman flag
29_Science_and_Space|A P J Abdul Kalam|ଏପିଜେ ଅବଦୁଲ କଲାମ|एपीजे अब्दुल कलाम|a p j abdul kalam
29_Science_and_Space|Aryabhata|ଆର୍ଯ୍ୟଭଟ୍ଟ|आर्यभट्ट|Aryabhata
29_Science_and_Space|asteroid|କ୍ଷୁଦ୍ରଗ୍ରହ|क्षुद्रग्रह|asteroid
29_Science_and_Space|Subhas Chandra Bose|ସୁଭାଷ ଚନ୍ଦ୍ର ବୋଷ|सुभाष चंद्र बोस|Subhas Chandra Bose
29_Science_and_Space|comet|ଧୂମକେତୁ|धूमकेतु|comet
29_Science_and_Space|Marie Curie|ମେରି କ୍ୟୁରି|मैरी क्यूरी|Marie Curie
29_Science_and_Space|C V Raman|ସି ଭି ରମଣ|सी वी रमन|C V Raman
29_Science_and_Space|Charles Darwin|ଚାର୍ଲ୍ସ ଡାରୱିନ|चार्ल्स डार्विन|Charles Darwin
29_Science_and_Space|Earth|ପୃଥିବୀ|पृथ्वी|planet earth
29_Science_and_Space|Albert Einstein|ଆଲବର୍ଟ ଆଇନଷ୍ଟାଇନ|अल्बर्ट आइंस्टीन|Albert Einstein
29_Science_and_Space|galaxy|ଗ୍ୟାଲାକ୍ସି|मंदाकिनी|galaxy
29_Science_and_Space|Galileo Galilei|ଗାଲିଲିଓ|गैलीलियो|Galileo Galilei
29_Science_and_Space|Jagadish Chandra Bose|ଜଗଦୀଶ ଚନ୍ଦ୍ର ବୋଷ|जगदीश चंद्र बोस|Jagadish Chandra Bose
29_Science_and_Space|Jupiter|ବୃହସ୍ପତି|बृहस्पति|planet jupiter
29_Science_and_Space|Mars|ମଙ୍ଗଳ|मंगल|planet mars
29_Science_and_Space|Mercury|ବୁଧ|बुध|planet mercury
29_Science_and_Space|meteor|ଉଲ୍କା|उल्का|meteor
29_Science_and_Space|meteorite|ଉଲ୍କାପିଣ୍ଡ|उल्कापिंड|meteorite
29_Science_and_Space|moon|ଚନ୍ଦ୍ର|चाँद|moon
29_Science_and_Space|Neptune|ବରୁଣ|वरुण|planet neptune
29_Science_and_Space|Isaac Newton|ଆଇଜାକ ନିଉଟନ|आइज़ैक न्यूटन|Isaac Newton
29_Science_and_Space|Saturn|ଶନି|शनि|planet saturn
29_Science_and_Space|star|ତାରା|तारा|stars night sky
29_Science_and_Space|sun|ସୂର୍ଯ୍ୟ|सूरज|sun
29_Science_and_Space|Nikola Tesla|ନିକୋଲା ଟେସଲା|निकोला टेस्ला|Nikola Tesla
29_Science_and_Space|Uranus|ୟୁରେନସ|अरुण|planet uranus
29_Science_and_Space|Venus|ଶୁକ୍ର|शुक्र|planet venus
29_Science_and_Space|Pluto|ପ୍ଲୁଟୋ|प्लूटो|planet pluto
29_Science_and_Space|Milky Way|ଛାୟାପଥ|आकाशगंगा|Milky Way
29_Science_and_Space|solar system|ସୌରମଣ୍ଡଳ|सौरमंडल|solar system
29_Science_and_Space|planet|ଗ୍ରହ|ग्रह|planet
29_Science_and_Space|satellite|ଉପଗ୍ରହ|उपग्रह|satellite
29_Science_and_Space|telescope|ଦୂରବୀକ୍ଷଣ ଯନ୍ତ୍ର|दूरबीन|telescope
29_Science_and_Space|microscope|ଅଣୁବୀକ୍ଷଣ ଯନ୍ତ୍ର|सूक्ष्मदर्शी|microscope
29_Science_and_Space|Rakesh Sharma|ରାକେଶ ଶର୍ମା|राकेश शर्मा|Rakesh Sharma
29_Science_and_Space|Kalpana Chawla|କଳ୍ପନା ଚାୱଲା|कल्पना चावला|Kalpana Chawla
29_Science_and_Space|Sunita Williams|ସୁନିତା ୱିଲିୟମ୍ସ|सुनीता विलियम्स|Sunita Williams
29_Science_and_Space|Yuri Gagarin|ୟୁରୀ ଗାଗାରିନ|यूरी गागरिन|Yuri Gagarin
29_Science_and_Space|Neil Armstrong|ନିଲ ଆର୍ମଷ୍ଟ୍ରଙ୍ଗ|नील आर्मस्ट्रांग|Neil Armstrong
29_Science_and_Space|ISRO|ଇସ୍ରୋ|इसरो|ISRO
29_Science_and_Space|Chandrayaan|ଚନ୍ଦ୍ରଯାନ|चंद्रयान|Chandrayaan
29_Science_and_Space|Mangalyaan|ମଙ୍ଗଳଯାନ|मंगलयान|Mangalyaan
29_Science_and_Space|Aditya L1|ଆଦିତ୍ୟ ଏଲ୍ ୱାନ|आदित्य एल वन|Aditya L1
29_Science_and_Space|Vikram Sarabhai|ବିକ୍ରମ ସାରାଭାଇ|विक्रम साराभाई|Vikram Sarabhai
29_Science_and_Space|Homi Bhabha|ହୋମି ଭାବା|होमी भाभा|Homi Bhabha
29_Science_and_Space|Srinivasa Ramanujan|ଶ୍ରୀନିବାସ ରାମାନୁଜନ|श्रीनिवास रामानुजन|Srinivasa Ramanujan
29_Science_and_Space|Stephen Hawking|ଷ୍ଟିଫେନ ହକିଙ୍ଗ|स्टीफन हॉकिंग|Stephen Hawking
29_Science_and_Space|Thomas Edison|ଥୋମାସ ଏଡିସନ|थॉमस एडिसन|Thomas Edison
29_Science_and_Space|Alexander Graham Bell|ଆଲେକ୍ସାଣ୍ଡର ଗ୍ରାହାମ ବେଲ|अलेक्जेंडर ग्राहम बेल|Alexander Graham Bell
29_Science_and_Space|Nicolaus Copernicus|କୋପରନିକସ|कोपरनिकस|Nicolaus Copernicus
29_Science_and_Space|Louis Pasteur|ଲୁଇ ପାଷ୍ଟର|लुई पाश्चर|Louis Pasteur
29_Science_and_Space|Wright Brothers|ରାଇଟ ଭାଇ|राइट बंधु|Wright Brothers
29_Science_and_Space|black hole|କୃଷ୍ଣ ଗହ୍ୱର|ब्लैक होल|black hole
29_Science_and_Space|solar eclipse|ସୂର୍ଯ୍ୟ ଗ୍ରହଣ|सूर्य ग्रहण|solar eclipse
29_Science_and_Space|lunar eclipse|ଚନ୍ଦ୍ର ଗ୍ରହଣ|चंद्र ग्रहण|lunar eclipse
29_Science_and_Space|rainbow|ଇନ୍ଦ୍ରଧନୁ|इंद्रधनुष|rainbow
29_Science_and_Space|volcano|ଜ୍ୱାଳାମୁଖୀ|ज्वालामुखी|volcano
29_Science_and_Space|lightning|ବିଜୁଳି|बिजली|lightning
29_Science_and_Space|magnet|ଚୁମ୍ବକ|चुंबक|magnet
29_Science_and_Space|atom|ପରମାଣୁ|परमाणु|atom
29_Science_and_Space|DNA|ଡିଏନଏ|डीएनए|DNA
29_Science_and_Space|gravity|ମାଧ୍ୟାକର୍ଷଣ|गुरुत्वाकर्षण|gravity
29_Science_and_Space|space station|ମହାକାଶ ଷ୍ଟେସନ|अंतरिक्ष स्टेशन|space station
29_Science_and_Space|solar panel|ସୌର ପ୍ୟାନେଲ|सोलर पैनल|solar panel
29_Science_and_Space|constellation|ନକ୍ଷତ୍ରମଣ୍ଡଳ|तारामंडल|constellation
29_Science_and_Space|pole star|ଧ୍ରୁବତାରା|ध्रुव तारा|pole star
"""
WORDS = [tuple(l.split("|", 4)) for l in DATA.strip().split("\n")]   # (chapter, english, odia, hindi, search term)

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"]

def http(url, timeout=12, maxb=6 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": random.choice(UAS), "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close", "Cache-Control": "no-cache"})
    with urllib.request.build_opener().open(req, timeout=timeout) as r:
        data = r.read(maxb + 1)
        if len(data) > maxb: raise ValueError("too big")
        return data, r.headers.get("Content-Type", "")

# ---------------- search: ONE term per word, page by page ----------------
SEARCH_SEM = threading.Semaphore(SEARCH_PARALLEL)
PAGE_STEP = 35           # Bing 'first=' step between pages

def search_page(q, folder, page):
    """image urls of ONE Bing result page for the search term q"""
    flt = "&qft=" + urllib.parse.quote("+filterui:photo-photo") if any(k in folder.lower() for k in PHOTO_CHAPTERS) else ""
    with SEARCH_SEM:
        html, _ = http("https://www.bing.com/images/search?adlt=strict&form=HDRSC3&first=" + str(1 + PAGE_STEP * page) + "&count=50&cvid="
                       + uuid.uuid4().hex.upper() + flt + "&q=" + urllib.parse.quote(q))
    html = html.decode("utf-8", "ignore"); out = []
    for m in re.finditer(r'murl(?:&quot;|")\s*:\s*(?:&quot;|")(https?:[^"<>\s]+?)(?:&quot;|")', html):
        u = (m.group(1).replace("&amp;", "&").replace("\\u0026", "&").replace("\\u003d", "=")
             .replace("\\u003f", "?").replace("\\/", "/"))
        if u not in out: out.append(u)
    return out

# ---------------- pictures ----------------
def fetch_picture(url):
    """one candidate -> PIL image (RGB, transparent parts on white, max 400 px) or None"""
    try:
        data, ctype = http(url)
        if ctype and not ctype.lower().startswith("image/"): return None
        im = Image.open(io.BytesIO(data)); im.load()
        if min(im.size) < MIN_SIDE: return None
        if max(im.size) / float(min(im.size)) > 3: return None          # banners / strips
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((400, 400))
        return im
    except Exception:
        return None

def ahash(im):
    g = im.convert("L").resize((8, 8)); px = list(g.tobytes()); avg = sum(px) / 64.0
    return sum(1 << i for i, v in enumerate(px) if v > avg)

def same(a, b):
    return bin(a ^ b).count("1") <= 4

# ---------------- word state (+ resume) ----------------
def key_of(it):  return "%s|%s|%s" % (it[0], it[1], it[4])        # changing the search term = a new word -> it is downloaded again
def wid_of(it):  return hashlib.md5(key_of(it).encode("utf-8")).hexdigest()[:10]
def file_of(it):
    name = re.sub(r'[\\/:*?"<>|]', "", "%s_%s_%s" % (it[1], it[2], it[3])).strip()
    return os.path.join(OUT, it[0], name + ".webp")

if os.path.exists("assets.zip") and not os.path.isdir(OUT) and not FRESH:        # previous result given next to the script -> resume
    try:
        zipfile.ZipFile("assets.zip").extractall(".")
        print("Previous assets.zip found and unpacked -> only unfinished words will be downloaded again")
    except Exception as e:
        print("could not unpack old assets.zip:", e)
if FRESH:
    for d in (OUT, CACHE_KEEP): shutil.rmtree(d, ignore_errors=True)
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
STATE = {}
if os.path.exists(STATE_FILE):
    try: STATE = json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception: STATE = {}
STATE_LOCK = threading.Lock()
def save_state():
    with STATE_LOCK:
        tmp = STATE_FILE + ".tmp"
        json.dump(STATE, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, STATE_FILE)

class W:
    def __init__(s, i, item, ci):
        s.i, s.ci, s.item = i, ci, item
        s.chapter, s.en, s.od, s.hi, s.q = item
        s.key, s.wid, s.keep_dir, s.out = key_of(item), wid_of(item), os.path.join(CACHE_KEEP, wid_of(item)), file_of(item)
        s.good = []                       # exact pictures: (probability, PIL image)
        s.best = None                     # best NOT-exact picture (only used when a word has no exact picture at all)
        s.hashes, s.seen = [], set()
        s.page, s.pages_run, s.checked, s.err = 0, 0, 0, ""
        s.status, s.conf, s.done = "NEW", 0.0, False

chapters = {}
for it in WORDS: chapters.setdefault(it[0], []).append(it)
words = []
for ch in sorted(chapters):
    for ci, it in enumerate(chapters[ch]): words.append(W(len(words), it, ci))
redo = set(x.lower() for x in REDO)
for w in words:
    st = STATE.get(w.key)
    if not st or w.en.lower() in redo: continue
    w.page, w.checked, w.status, w.conf = st.get("page", 0), st.get("checked", 0), st.get("status", "NEW"), st.get("conf", 0.0)
    w.seen = set(st.get("seen", []))
    if st.get("status") == "OK" and os.path.exists(w.out):
        w.done = True                                                         # verified before -> never touched again
    elif os.path.isdir(w.keep_dir):                                           # unfinished: reload its exact pictures, continue deeper
        for fn in sorted(os.listdir(w.keep_dir)):
            try:
                im = Image.open(os.path.join(w.keep_dir, fn)); im.load(); im = im.convert("RGB")
                w.good.append((float(fn.split("_")[0]) / 1000.0, im)); w.hashes.append(ahash(im))
            except Exception: pass
todo = [w for w in words if not w.done]
print("Words: %d in %d chapters | already verified: %d | to do now: %d" % (len(words), len(chapters), len(words) - len(todo), len(todo)))

img_pool = ThreadPoolExecutor(IMG_WORKERS)

# ---------------- the checker (CLIP) - only when VERIFY = True ----------------
if VERIFY and todo:
    import torch
    from transformers import CLIPModel, CLIPProcessor
    torch.set_num_threads(os.cpu_count() or 4)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("Checker running on:", dev)
    model = CLIPModel.from_pretrained(CLIP_MODEL).to(dev).eval()
    proc = CLIPProcessor.from_pretrained(CLIP_MODEL)
    CLIP_LOCK = threading.Lock()          # one picture batch at a time in the checker, while all other words keep downloading

    def _tensor(x):
        if torch.is_tensor(x): return x
        p = getattr(x, "pooler_output", None)
        return p if p is not None else x[0]

    def text_feats(prompts):
        with torch.no_grad():
            t = proc(text=prompts, return_tensors="pt", padding=True, truncation=True).to(dev)
            f = _tensor(model.get_text_features(**t)); return f / f.norm(dim=-1, keepdim=True)

    def image_feats(imgs):
        with torch.no_grad():
            x = proc(images=imgs, return_tensors="pt").to(dev)
            f = _tensor(model.get_image_features(**x)); return f / f.norm(dim=-1, keepdim=True)

    def word_feats(items):
        """3 different sentences per word (built from the search term), averaged -> more exact matching"""
        fs = [text_feats([tpl % it[4] for it in items]) for tpl in ("a photo of %s", "a picture of %s", "%s")]
        f = sum(fs) / len(fs)
        return f / f.norm(dim=-1, keepdim=True)

    need = set(w.chapter for w in todo)
    TXT = {ch: word_feats(items) for ch, items in chapters.items() if ch in need}     # the checker compares a picture with ALL words of its chapter

    def _tok(s):
        return set(t[:-1] if t.endswith("s") and len(t) > 3 else t for t in s.lower().split())
    def sibling(a, b):
        """finger/fingers, dates/dried dates ... CLIP cannot separate them, so either one counts as a match"""
        A, B = _tok(a), _tok(b)
        return A <= B or B <= A
    SIB = {ch: [[sibling(x[1], y[1]) for y in items] for x in items] for ch, items in chapters.items() if ch in need}

    def classify(w, imgs):
        """-> [(probability of its own word, exact?)] for the given pictures"""
        with CLIP_LOCK:
            probs = (100.0 * image_feats(imgs) @ TXT[w.chapter].T).softmax(dim=-1).cpu()
        res = []
        for pr in probs:
            v = float(pr[w.ci]); top = int(pr.argmax())
            res.append((v, v >= GOOD_PROB and (top == w.ci or SIB[w.chapter][w.ci][top])))   # its own word must be the checker's #1
        return res
else:
    def classify(w, imgs):
        return [(1.0, True) for _ in imgs]                                    # VERIFY = False: first pictures are accepted

# ---------------- ONE word: search -> download chunk -> check at once -> repeat until 4 exact pictures ----------------
def process_word(w):
    fails = 0
    while len(w.good) < GRID and w.pages_run < MAX_PAGES and fails < 3:
        try:
            urls = search_page(w.q, w.chapter, w.page)
        except Exception as e:
            fails += 1; w.err = "search: %s" % e; time.sleep(1.5 * fails + random.random()); continue
        fails = 0; w.pages_run += 1; w.page += 1
        urls = [u for u in urls if u not in w.seen]
        if not urls: w.err = "no new results"; continue
        w.seen.update(urls); w.err = ""
        for s in range(0, len(urls), CHUNK):
            imgs = [im for im in img_pool.map(fetch_picture, urls[s:s + CHUNK]) if im is not None]
            fresh = []
            for im in imgs:
                h = ahash(im)
                if any(same(h, o) for o in w.hashes): continue               # no duplicates
                w.hashes.append(h); fresh.append(im)
            if not fresh: continue
            for im, (v, ok) in zip(fresh, classify(w, fresh)):               # checked INSTANTLY after the download
                w.checked += 1
                if ok: w.good.append((v, im))
                elif w.best is None or v > w.best[0]: w.best = (v, im)
            if len(w.good) >= GRID: break                                    # 4 exact pictures -> stop, no more downloads for this word
    if not w.good and w.best is None and not w.err: w.err = "no usable picture"

# ---------------- merge the pictures of ONE word into ONE image ----------------
def to_tile(im):
    """whole picture (no cropping) centred on a white TILE x TILE square"""
    s = float(TILE) / max(im.size)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    tile = Image.new("RGB", (TILE, TILE), (255, 255, 255))
    tile.paste(im, ((TILE - im.width) // 2, (TILE - im.height) // 2))
    return tile

def merge4(tiles):
    n = min(len(tiles), 4)                                       # 1 picture: single, 2: side by side, 3-4: 2x2
    cols = 1 if n == 1 else 2
    rows = 1 if n <= 2 else 2
    sheet = Image.new("RGB", (TILE * cols, TILE * rows), (255, 255, 255))
    for i, t in enumerate(tiles[:4]):
        sheet.paste(t, ((i % 2) * TILE, (i // 2) * TILE))
    buf = io.BytesIO(); sheet.save(buf, "WEBP", quality=QUALITY, method=6)
    return buf.getvalue()

def finish_word(w):
    """result of ONE word is written at once (WebP + state), so nothing is lost if the run stops"""
    good = sorted(w.good, key=lambda c: -c[0])[:GRID]
    pick = [im for _, im in good] or ([w.best[1]] if w.best else [])
    if pick:
        os.makedirs(os.path.dirname(w.out), exist_ok=True)
        open(w.out, "wb").write(merge4([to_tile(im) for im in pick]))
    n = len(good)
    w.status = "FAILED" if not pick else ("OK" if n >= GRID else ("PARTIAL" if n >= 1 else "NO_MATCH"))
    w.conf = sum(v for v, _ in good) / n if n else (w.best[0] if w.best else 0.0)
    shutil.rmtree(w.keep_dir, ignore_errors=True)
    if w.status != "OK" and good:                                # keep the exact pictures so a later run only needs to find the missing ones
        os.makedirs(w.keep_dir, exist_ok=True)
        for k, (v, im) in enumerate(good): im.save(os.path.join(w.keep_dir, "%04d_%d.jpg" % (int(v * 1000), k)), "JPEG", quality=88)
    with STATE_LOCK:
        STATE[w.key] = {"status": w.status, "n_good": n, "conf": round(w.conf, 3), "page": w.page, "checked": w.checked,
                        "seen": sorted(w.seen)[-400:] if w.status != "OK" else [], "q": w.q, "err": w.err,
                        "en": w.en, "od": w.od, "hi": w.hi, "chapter": w.chapter}
    w.done = True

def run_word(w):
    process_word(w); finish_word(w)

# ================================ RUN: every word = download + instant check + merge ================================
t0 = time.time()
print("\n=== %s %d words (one search term each, checked right after download) ..." % ("verifying" if VERIFY else "downloading", len(todo)))
done = 0
with ThreadPoolExecutor(WORD_WORKERS) as wp:
    futs = [wp.submit(run_word, w) for w in todo]
    for f in as_completed(futs):
        try: f.result()
        except Exception as e: print("   error:", e)
        done += 1
        if done % 50 == 0 or done == len(todo):
            ok = sum(1 for w in todo if w.done and w.status == "OK")
            print("   %d/%d words finished, %d verified (4 exact pictures)  [%.0f s]" % (done, len(todo), ok, time.time() - t0))
            save_state()
save_state()

# ================================ report + zip ================================
report = []
for w in words:
    st = STATE.get(w.key, {})
    report.append([w.chapter, w.en, w.od, w.hi, st.get("status", "FAILED"), st.get("n_good", 0), st.get("conf", 0), st.get("page", 0),
                   w.q, st.get("err", "")])
with open("verify_report.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([["chapter", "english", "odia", "hindi", "status", "exact_pictures", "confidence", "bing_pages_used", "search_term", "error"]] + report)
bad = [r for r in report if r[4] in ("NO_MATCH", "FAILED")]
chk = [r for r in report if r[4] == "PARTIAL"]
print("\nFinished in %.1f min: %d OK (4 pictures), %d PARTIAL (1-3 pictures), %d NO_MATCH/FAILED" % (
      (time.time() - t0) / 60, len(report) - len(bad) - len(chk), len(chk), len(bad)))
for r in bad + chk: print("  not verified yet:", r[0], r[1], "|", r[8], "|", r[4], r[9])
if bad or chk: print("-> run the script again: ONLY these words are downloaded + checked again (deeper Bing pages). Or change their search term in the list.")

with zipfile.ZipFile("assets.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for top in (OUT, CACHE_KEEP):
        for root, ds, fs in os.walk(top):
            for fn in sorted(fs):
                p = os.path.join(root, fn); z.write(p, p.replace(os.sep, "/"))
    z.write("verify_report.csv"); z.write(STATE_FILE)
print("assets.zip: %.1f MB" % (os.path.getsize("assets.zip") / 1048576))
try:
    from google.colab import files
    files.download("assets.zip")
except ImportError:
    print("Not in Colab: assets.zip is in the current folder")
