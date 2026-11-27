# === ONE cell (Colab: GPU not needed for this part, CPU is fine) ================================================
# SEARCH   Google Images with the PNG filter (like "tiger animal type:png"); Bing (transparent filter) is the fallback
# PHASE 1  download ALL words of ALL chapters at the same time (full speed)
# PHASE 2  verify EVERY picture with CLIP (image-text AI) -> the 4 best pictures of each word are chosen
# PHASE 3  ONLY words that are not verified are downloaded again (new search words) -> verified again, repeated
# PHASE 4  the 4 best pictures of each word: BACKGROUND REMOVED (rembg) -> WHITE background -> cropped to the subject
#          -> merged into ONE 2x2 picture -> compressed WebP  english_odia_hindi.webp
#          at the end assets.zip (assets/<chapter>/*.webp + verify_report.csv) is created / downloaded.
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "transformers", "pillow", "rembg", "onnxruntime"], check=False)

import io, os, re, json, time, csv, uuid, random, shutil, zipfile, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

CANDIDATES = 16          # new pictures per word and round; the best 4 are kept
WORD_WORKERS = 48        # words downloaded at the same time (all chapters together)
IMG_WORKERS = 160        # picture downloads at the same time
SEARCH_PARALLEL = 6      # search-page requests at the same time (Google blocks too many at once)
MAX_ROUNDS = 10          # retry rounds for unverified words
NOIMG_EXTRA = 15         # extra rounds ONLY for words that have no picture at all
GRID, TILE, QUALITY = 4, 400, 70   # 4 pictures, 400 px tiles -> 800x800 merged WebP
MIN_SIDE = 150           # smaller pictures are rejected
REMBG_MODEL = "u2net"    # "u2net" = best quality, "u2netp" = 4x faster / smaller, "isnet-general-use" = sharper edges
REMBG_WORKERS = 3        # background removals at the same time
BATCH = 128              # CLIP batch size
CACHE, OUT = "cache", "assets"
PHOTO_CHAPTERS = ("fruit", "vegetable", "flower", "animal", "household", "transport", "profession", "computer", "body")

DATA = """07_Colors|black|କଳା|काला|black color
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
07_Colors|mustard|ସୋରିଷ ରଙ୍ଗ|सरसों|mustard yellow color
07_Colors|olive green|ଅଲିଭ ସବୁଜ|जैतूनी हरा|olive green color
07_Colors|bronze|ବ୍ରୋଞ୍ଜ|काँस्य|bronze color
07_Colors|rainbow|ଇନ୍ଦ୍ରଧନୁ|इंद्रधनुष|rainbow colors
07_Colors|multicolor|ବହୁରଙ୍ଗୀ|बहुरंगी|multicolor colorful
08_Shapes|circle|ବୃତ୍ତ|वृत्त|circle shape geometry
08_Shapes|cone|ଶଙ୍କୁ|शंकु|cone shape geometry
08_Shapes|octagon|ଅଷ୍ଟଭୁଜ|अष्टभुज|octagon shape geometry
08_Shapes|cube|ଘନ|घन|cube shape geometry
08_Shapes|cylinder|ସ୍ତମ୍ଭ|बेलन|cylinder shape geometry
08_Shapes|hexagon|ଷଡ଼ଭୁଜ|षट्भुज|hexagon shape geometry
08_Shapes|oval|ଅଣ୍ଡାକାର|अंडाकार|oval shape geometry
08_Shapes|pentagon|ପଞ୍ଚଭୁଜ|पंचभुज|pentagon shape geometry
08_Shapes|prism|ପ୍ରିଜ୍ମ|प्रिज्म|prism shape geometry
08_Shapes|rectangle|ଆୟତ|आयत|rectangle shape geometry
08_Shapes|rhombus|ସମଚତୁର୍ଭୁଜ|समचतुर्भुज|rhombus shape geometry
08_Shapes|square|ବର୍ଗ|वर्ग|square shape geometry
08_Shapes|triangle|ତ୍ରିଭୁଜ|त्रिभुज|triangle shape geometry
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
09_Fruits|almond|ବାଦାମ|बादाम|almond fruit
09_Fruits|apple|ସେଓ|सेब|apple fruit
09_Fruits|banana|କଦଳୀ|केला|banana fruit
09_Fruits|betel nut|ଗୁଆ|सुपारी|betel nut areca
09_Fruits|blackberry|କଳା ବେରି|ब्लैकबेरी|blackberry fruit
09_Fruits|cashew nut|କାଜୁ|काजू|cashew nut fruit
09_Fruits|cherry|ଚେରି|चेरी|cherry fruit
09_Fruits|coconut|ନଡ଼ିଆ|नारियल|coconut fruit
09_Fruits|custard apple|ସୀତାଫଳ|सीताफल|custard apple fruit
09_Fruits|dried dates|ଛୁହାରା|छुहारा|dried dates fruit
09_Fruits|flax seeds|ଅଳସି|अलसी|flax seeds fruit
09_Fruits|grapes|ଅଙ୍ଗୁର|अंगूर|grapes fruit
09_Fruits|groundnut|ଚିନାବାଦାମ|मूंगफली|peanut
09_Fruits|guava|ପିଜୁଳି|अमरूद|guava fruit
09_Fruits|jackfruit|ପଣସ|कटहल|jackfruit fruit
09_Fruits|kiwi|କିୱି|कीवी|kiwi fruit
09_Fruits|lemon|ଲେମ୍ବୁ|नींबू|lemon fruit
09_Fruits|litchi|ଲିଚି|लीची|lychee fruit
09_Fruits|mango|ଆମ୍ବ|आम|mango fruit
09_Fruits|muskmelon|ଖରଭୁଜ|खरबूजा|muskmelon fruit
09_Fruits|orange|କମଳା|संतरा|orange fruit
09_Fruits|papaya|ଅମୃତଭଣ୍ଡା|पपीता|papaya fruit
09_Fruits|pear|ନାସପାତି|नाशपाती|pear fruit
09_Fruits|pineapple|ଅନାନାସ|अनानास|pineapple fruit
09_Fruits|pistachio|ପିସ୍ତା|पिस्ता|pistachio fruit
09_Fruits|pomegranate|ଡାଳିମ୍ବ|अनार|pomegranate fruit
09_Fruits|raisin|କିସମିସ|किशमिश|raisin fruit
09_Fruits|sapodilla|ସପୋଟା|चीकू|sapodilla chikoo fruit
09_Fruits|sugarcane|ଆଖୁ|गन्ना|sugarcane fruit
09_Fruits|tamarind|ତେନ୍ତୁଳି|इमली|tamarind fruit
09_Fruits|walnuts|ଆଖରୋଟ|अखरोट|walnut
09_Fruits|watermelon|ତରଭୁଜ|तरबूज|watermelon fruit
09_Fruits|apricot|ଖୁବାନି|खुबानी|apricot fruit
09_Fruits|plum|ଆଳୁବୁଖରା|आलूबुखारा|plum fruit
09_Fruits|peach|ପିଚ୍|आड़ू|peach fruit
09_Fruits|strawberry|ଷ୍ଟ୍ରବେରି|स्ट्रॉबेरी|strawberry fruit
09_Fruits|blueberry|ବ୍ଲୁବେରି|ब्लूबेरी|blueberry fruit
09_Fruits|raspberry|ରାସବେରି|रास्पबेरी|raspberry fruit
09_Fruits|mulberry|ତୁତ|शहतूत|mulberry fruit
09_Fruits|gooseberry|ଅଁଳା|आंवला|amla indian gooseberry fruit
09_Fruits|black plum|ଜାମୁ|जामुन|jamun black plum fruit
09_Fruits|wood apple|କଇଥ|कैथ|wood apple fruit
09_Fruits|bael|ବେଲ|बेल|bael fruit
09_Fruits|star fruit|କର୍ମଙ୍ଗା|कमरख|star fruit carambola
09_Fruits|fig|ଡିମ୍ବିରି|अंजीर|fig fruit
09_Fruits|dragon fruit|ଡ୍ରାଗନ ଫ୍ରୁଟ|ड्रैगन फ्रूट|dragon fruit fruit
09_Fruits|avocado|ଆଭୋକାଡୋ|एवोकाडो|avocado fruit
09_Fruits|sweet lime|ମୋସମ୍ବି|मौसंबी|sweet lime mosambi fruit
09_Fruits|grapefruit|ଗ୍ରେପ୍‌ଫ୍ରୁଟ|चकोतरा|grapefruit fruit
09_Fruits|passion fruit|ପାସନ ଫ୍ରୁଟ|पैशन फ्रूट|passion fruit fruit
09_Fruits|cranberry|କ୍ରାନବେରି|क्रैनबेरी|cranberry fruit
09_Fruits|jujube|ବରକୋଳି|बेर|jujube ber fruit
09_Fruits|dates|ଖଜୁରୀ|खजूर|dates fruit
09_Fruits|chestnut|ଚେଷ୍ଟନଟ୍|चेस्टनट|chestnut nut
09_Fruits|olive|ଜଳପାଇ|जैतून|olive fruit
09_Fruits|persimmon|ପର୍ସିମନ|पर्सिमन|persimmon fruit
09_Fruits|nectarine|ନେକ୍ଟାରିନ|नेक्टराइन|nectarine fruit
09_Fruits|tangerine|ଟାଞ୍ଜେରିନ|टैंजेरीन|tangerine fruit
09_Fruits|honeydew melon|ହନିଡ୍ୟୁ ମେଲନ|हनीड्यू खरबूजा|honeydew melon fruit
09_Fruits|fox nut|ମଖାନା|मखाना|makhana fox nut
09_Fruits|hazelnut|ହେଜେଲନଟ୍|हेज़लनट|hazelnut fruit
09_Fruits|palmyra fruit|ତାଳ|ताड़ का फल|palmyra palm fruit ice apple
09_Fruits|dry fruits|ଶୁଖିଲା ଫଳ|सूखे मेवे|mixed dry fruits
10_Vegetables|beans|ବିନ୍ସ|बीन्स|green beans vegetable
10_Vegetables|beetroot|ବିଟ|चुकंदर|beetroot vegetable
10_Vegetables|bitter gourd|କଲରା|करेला|bitter gourd vegetable
10_Vegetables|bottle gourd|ଲାଉ|लौकी|bottle gourd vegetable
10_Vegetables|brinjal|ବାଇଗଣ|बैंगन|brinjal vegetable
10_Vegetables|broccoli|ବ୍ରୋକୋଲି|ब्रोकली|broccoli vegetable
10_Vegetables|cabbage|ବନ୍ଧାକୋବି|पत्ता गोभी|cabbage vegetable
10_Vegetables|capsicum|କ୍ୟାପ୍ସିକମ|शिमला मिर्च|capsicum vegetable
10_Vegetables|carrot|ଗାଜର|गाजर|carrot vegetable
10_Vegetables|cauliflower|ଫୁଲକୋବି|फूलगोभी|cauliflower vegetable
10_Vegetables|chilly|ଲଙ୍କା|मिर्च|green chilli
10_Vegetables|coriander|ଧନିଆ|धनिया|coriander vegetable
10_Vegetables|corn|ମକା|मक्का|corn vegetable
10_Vegetables|cucumber|କାକୁଡ଼ି|खीरा|cucumber vegetable
10_Vegetables|curry leaf|ଭୃଷଙ୍ଗ|करी पत्ता|curry leaf vegetable
10_Vegetables|french beans|ଫ୍ରେଞ୍ଚ ବିନ୍ସ|फ्रेंच बीन्स|french beans vegetable
10_Vegetables|garlic|ରସୁଣ|लहसुन|garlic vegetable
10_Vegetables|ginger|ଅଦା|अदरक|ginger vegetable
10_Vegetables|ladyfinger|ଭେଣ୍ଡି|भिंडी|okra ladyfinger vegetable
10_Vegetables|mushroom|ଛତୁ|मशरूम|mushroom vegetable
10_Vegetables|onion|ପିଆଜ|प्याज|onion vegetable
10_Vegetables|parwal|ପୋଟଳ|परवल|pointed gourd parwal vegetable
10_Vegetables|peas|ମଟର|मटर|green peas vegetable
10_Vegetables|potato|ଆଳୁ|आलू|potato vegetable
10_Vegetables|pumpkin seeds|କଖାରୁ ବିହନ|कद्दू के बीज|pumpkin seeds food
10_Vegetables|pumpkin|କଖାରୁ|कद्दू|pumpkin vegetable
10_Vegetables|radish|ମୂଳା|मूली|radish vegetable
10_Vegetables|spinach|ପାଳଙ୍ଗ|पालक|spinach vegetable
10_Vegetables|sweet potato|ରଙ୍ଗା ଆଳୁ|शकरकंद|sweet potato vegetable
10_Vegetables|tomato|ଟମାଟୋ|टमाटर|tomato vegetable
10_Vegetables|lettuce|ଲେଟୁସ|सलाद पत्ता|lettuce vegetable
10_Vegetables|celery|ସେଲେରି|अजमोदा|celery vegetable
10_Vegetables|turnip|ଶଳଗମ|शलजम|turnip vegetable
10_Vegetables|yam|ଓଲ|जिमीकंद|elephant foot yam vegetable
10_Vegetables|taro|ସରୁ|अरबी|taro colocasia vegetable
10_Vegetables|ridge gourd|ଝୁଙ୍ଗା|तोरई|ridge gourd vegetable
10_Vegetables|snake gourd|ଚିଚିଣ୍ଡା|चिचिंडा|snake gourd vegetable
10_Vegetables|drumstick|ସଜନା ଛୁଇଁ|सहजन की फली|drumstick moringa vegetable
10_Vegetables|raw banana|କଞ୍ଚା କଦଳୀ|कच्चा केला|raw banana vegetable
10_Vegetables|raw papaya|କଞ୍ଚା ଅମୃତଭଣ୍ଡା|कच्चा पपीता|raw papaya vegetable
10_Vegetables|spring onion|ପିଆଜ କଲି|हरा प्याज|spring onion vegetable
10_Vegetables|mint|ପୋଦିନା|पुदीना|mint leaves
10_Vegetables|fenugreek|ମେଥି|मेथी|fenugreek leaves methi
10_Vegetables|mustard greens|ସୋରିଷ ଶାଗ|सरसों का साग|mustard greens vegetable
10_Vegetables|cluster beans|ଗୁଆର|ग्वार फली|cluster beans guar
10_Vegetables|broad beans|ଶିମ୍ବ|सेम|broad beans
10_Vegetables|sweet corn|ମିଠା ମକା|स्वीट कॉर्न|sweet corn vegetable
10_Vegetables|zucchini|ଜୁକିନି|ज़ुकीनी|zucchini vegetable
10_Vegetables|asparagus|ଆସ୍ପାରାଗସ|शतावरी|asparagus vegetable
10_Vegetables|turmeric|ହଳଦୀ|हल्दी|raw turmeric
10_Vegetables|ivy gourd|ତେଲକୁଚା|कुंदरू|ivy gourd tindora vegetable
10_Vegetables|banana flower|କଦଳୀ ଫୁଲ|केले का फूल|banana flower vegetable
10_Vegetables|soybean|ସୋୟାବିନ|सोयाबीन|soybean vegetable
10_Vegetables|red cabbage|ଲାଲ ବନ୍ଧାକୋବି|लाल पत्ता गोभी|red cabbage vegetable
10_Vegetables|kohlrabi|ଓଲକୋବି|गाँठ गोभी|kohlrabi vegetable
10_Vegetables|leafy greens|ଶାଗ|साग|leafy greens vegetable india
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
11_Flowers|saffron|କେସରୀ|केसरिया|saffron crocus flower
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
11_Flowers|night jasmine|ଶେଫାଳି|हरसिंगार|night jasmine parijat flower
11_Flowers|bakula|ବକୁଳ|मौलसिरी|bakula flower
11_Flowers|kadamba|କଦମ୍ବ|कदंब|kadamba flower
11_Flowers|kewda|କେତକୀ|केवड़ा|kewda flower
11_Flowers|peony|ପିଓନି|पियोनी|peony flower
11_Flowers|iris|ଆଇରିସ|आइरिस|iris flower
11_Flowers|gladiolus|ଗ୍ଲାଡିଓଲସ|ग्लैडियोलस|gladiolus flower
11_Flowers|aster|ଆଷ୍ଟର|एस्टर|aster flower
11_Flowers|hydrangea|ହାଇଡ୍ରାଞ୍ଜିଆ|हाइड्रेंजिया|hydrangea flower
11_Flowers|madhumalati|ମଧୁମାଳତୀ|मधुमालती|madhumalati rangoon creeper flower
11_Flowers|tagar|ଟଗର|टगर|tagar flower
11_Flowers|cherry blossom|ଚେରି ବ୍ଲସମ|चेरी ब्लॉसम|cherry blossom flower
11_Flowers|magnolia|ମ୍ୟାଗ୍ନୋଲିଆ|मैगनोलिया|magnolia flower
12_Animals|ant|ପିମ୍ପୁଡ଼ି|चींटी|ant insect
12_Animals|bear|ଭାଲୁ|भालू|bear animal
12_Animals|bee|ମହୁମାଛି|मधुमक्खी|honey bee insect
12_Animals|buffalo|ମଇଁଷି|भैंस|buffalo animal
12_Animals|bulbul|ବୁଲବୁଲ|बुलबुल|bulbul bird
12_Animals|bull|ଷଣ୍ଢ|बैल|bull animal
12_Animals|butterfly|ପ୍ରଜାପତି|तितली|butterfly animal
12_Animals|cat|ବିଲେଇ|बिल्ली|cat animal
12_Animals|cobra|ନାଗ|कोबरा|cobra animal
12_Animals|rooster|ଗଞ୍ଜା|मुर्गा|rooster bird
12_Animals|cockroach|ଅସରପା|तिलचट्टा|cockroach animal
12_Animals|cow|ଗାଈ|गाय|cow animal
12_Animals|crab|କଙ୍କଡ଼ା|केकड़ा|crab animal
12_Animals|cuckoo|କୋଇଲି|कोयल|cuckoo bird
12_Animals|dog|କୁକୁର|कुत्ता|dog animal
12_Animals|dolphin|ଡଲଫିନ|डॉल्फिन|dolphin animal
12_Animals|duck|ବତକ|बत्तख|duck animal
12_Animals|eagle|ଛଞ୍ଚାଣ|बाज|eagle animal
12_Animals|earthworm|କେଞ୍ଚୁଆ|केंचुआ|earthworm animal
12_Animals|eel|ବାମ|ईल|eel fish
12_Animals|elephant|ହାତୀ|हाथी|elephant animal
12_Animals|fox|ଶିଆଳ|लोमड़ी|fox animal
12_Animals|frog|ବେଙ୍ଗ|मेंढक|frog animal
12_Animals|swan|ରାଜହଂସ|राजहंस|swan bird
12_Animals|house sparrow|ଚଟିଆ|गौरैया|house sparrow bird
12_Animals|giraffe|ଜିରାଫ|जिराफ|giraffe animal
12_Animals|goat|ଛେଳି|बकरी|goat animal
12_Animals|grasshopper|ଝିଙ୍କା|टिड्डा|grasshopper animal
12_Animals|goose|ହଂସ|हंस|goose bird
12_Animals|hen|ମାଇକୁକୁଡ଼ା|मुर्गी|hen chicken
12_Animals|hippopotamus|ପାଣିହାତୀ|जलहस्ती|hippopotamus animal
12_Animals|horse|ଘୋଡ଼ା|घोड़ा|horse animal
12_Animals|jellyfish|ଜେଲିଫିଶ|जेलीफ़िश|jellyfish animal
12_Animals|kangaroo|କାଙ୍ଗାରୁ|कंगारू|kangaroo animal
12_Animals|crow|କାଉ|कौआ|crow bird
12_Animals|ladybug|ଲେଡିବଗ|लेडीबग|ladybug animal
12_Animals|lion|ସିଂହ|शेर|lion animal
12_Animals|lizard|ଝିଟିପିଟି|छिपकली|lizard animal
12_Animals|lobster|ଲବଷ୍ଟର|लॉबस्टर|lobster animal
12_Animals|kingfisher|ମାଛରଙ୍କା|मछरंगा|kingfisher bird
12_Animals|manatee|ମାନାଟି|मैनेटी|manatee animal
12_Animals|peahen|ମୟୂରୀ|मयूरी|peahen bird
12_Animals|monkey|ମାଙ୍କଡ଼|बंदर|monkey animal
12_Animals|mosquito|ମଶା|मच्छर|mosquito animal
12_Animals|octopus|ଅକ୍ଟୋପସ|ऑक्टोपस|octopus animal
12_Animals|oyster|ଶାମୁକା|सीप|oyster animal
12_Animals|peacock|ମୟୂର|मोर|peacock animal
12_Animals|owl|ପେଚା|उल्लू|owl bird
12_Animals|penguin|ପେଙ୍ଗୁଇନ|पेंगुइन|penguin animal
12_Animals|polar bear|ଧ୍ରୁବୀୟ ଭାଲୁ|ध्रुवीय भालू|polar bear animal
12_Animals|scorpion|ବିଛା|बिच्छू|scorpion animal
12_Animals|sea otter|ସମୁଦ୍ର ଓଟର|समुद्री ऊदबिलाव|sea otter animal
12_Animals|seahorse|ସମୁଦ୍ର ଘୋଡ଼ା|समुद्री घोड़ा|seahorse animal
12_Animals|seal|ସିଲ|सील|seal sea animal
12_Animals|shark|ଶାର୍କ|शार्क|shark animal
12_Animals|sheep|ମେଣ୍ଢା|भेड़|sheep animal
12_Animals|snake|ସାପ|साँप|snake animal
12_Animals|spider|ମାକଡ଼ସା|मकड़ी|spider animal
12_Animals|squid|ସ୍କ୍ୱିଡ|स्क्विड|squid animal
12_Animals|starfish|ତାରାମାଛ|स्टारफ़िश|starfish animal
12_Animals|termite|ଉଇ|दीमक|termite insect
12_Animals|tiger|ବାଘ|बाघ|tiger animal
12_Animals|turtle|କଇଁଛ|कछुआ|turtle animal
12_Animals|vulture|ଶାଗୁଣା|गिद्ध|vulture animal
12_Animals|whale|ତିମି|व्हेल|whale animal
12_Animals|wolf|ଗଧିଆ|भेड़िया|wolf animal
12_Animals|woodpecker|କାଠଠୋକା|कठफोड़वा|woodpecker animal
12_Animals|zebra|ଜେବ୍ରା|ज़ेबरा|zebra animal
12_Animals|rabbit|ଠେକୁଆ|खरगोश|rabbit animal
12_Animals|deer|ହରିଣ|हिरण|deer animal
12_Animals|camel|ଓଟ|ऊँट|camel animal
12_Animals|donkey|ଗଧ|गधा|donkey animal
12_Animals|pig|ଘୁଷୁରି|सूअर|pig animal
12_Animals|rat|ମୂଷା|चूहा|rat animal
12_Animals|squirrel|କାଠବିରାଳି|गिलहरी|squirrel animal
12_Animals|bat|ବାଦୁଡ଼ି|चमगादड़|bat flying mammal animal
12_Animals|leopard|ଚିତାବାଘ|तेंदुआ|leopard animal
12_Animals|cheetah|ଚିତା|चीता|cheetah animal
12_Animals|rhinoceros|ଗଣ୍ଡା|गैंडा|rhinoceros animal
12_Animals|panda|ପାଣ୍ଡା|पांडा|panda animal
12_Animals|koala|କୋଆଲା|कोआला|koala animal
12_Animals|gorilla|ଗୋରିଲା|गोरिल्ला|gorilla animal
12_Animals|chimpanzee|ଶିମ୍ପାଞ୍ଜି|चिंपैंज़ी|chimpanzee animal
12_Animals|crocodile|କୁମ୍ଭୀର|मगरमच्छ|crocodile animal
12_Animals|hyena|ହାଇନା|लकड़बग्घा|hyena animal
12_Animals|mongoose|ନକୁଳ|नेवला|mongoose animal
12_Animals|porcupine|ଶଜାରୁ|साही|porcupine animal
12_Animals|bison|ବାଇସନ|बाइसन|bison animal
12_Animals|yak|ୟାକ|याक|yak animal
12_Animals|llama|ଲାମା|लामा|llama animal
12_Animals|parrot|ଶୁଆ|तोता|parrot bird
12_Animals|pigeon|ପାରା|कबूतर|pigeon bird
12_Animals|flamingo|ଫ୍ଲେମିଙ୍ଗୋ|फ्लेमिंगो|flamingo animal
12_Animals|pelican|ପେଲିକାନ|पेलिकन|pelican animal
12_Animals|sarus crane|ସାରସ|सारस|sarus crane bird
12_Animals|heron|ବଗ|बगुला|heron bird
12_Animals|myna|ସାରିକା|मैना|myna bird
12_Animals|hornbill|ଧନେଶ|धनेश|hornbill bird
12_Animals|ostrich|ଅଷ୍ଟ୍ରିଚ|शुतुरमुर्ग|ostrich animal
12_Animals|turkey|ଟର୍କି|टर्की|turkey bird
12_Animals|fly|ମାଛି|मक्खी|housefly insect
12_Animals|dragonfly|ଫଡ଼ିଙ୍ଗ|ड्रैगनफ्लाई|dragonfly insect
12_Animals|caterpillar|ଶୁଆପୋକ|इल्ली|caterpillar insect
12_Animals|snail|ଶମ୍ବୁକ|घोंघा|snail animal
12_Animals|centipede|ଶତପଦୀ|कनखजूरा|centipede insect
12_Animals|moth|ପତଙ୍ଗ|पतंगा|moth insect
12_Animals|chameleon|କୃକଲାସ|गिरगिट|chameleon animal
12_Animals|python|ଅଜଗର|अजगर|python snake
12_Animals|monitor lizard|ଗୋଧି|गोह|monitor lizard animal
12_Animals|fish|ମାଛ|मछली|fish swimming
12_Animals|goldfish|ସୁନା ମାଛ|सुनहरी मछली|goldfish animal
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
12_Animals|walrus|ୱାଲରସ|वालरस|walrus animal
12_Animals|orca|ଓର୍କା|ऑर्का|orca killer whale
12_Animals|stingray|ଷ୍ଟିଙ୍ଗରେ|स्टिंग रे|stingray fish
12_Animals|clownfish|କ୍ଲାଉନଫିସ|क्लाउन फिश|clownfish
12_Animals|sea lion|ସି ଲାୟନ|सी लायन|sea lion
13_Body_Parts|arm|ବାହୁ|बाँह|arm human body part
13_Body_Parts|ear|କାନ|कान|ear human body part
13_Body_Parts|elbow|କୁହୁଣୀ|कोहनी|elbow human body part
13_Body_Parts|eye|ଆଖି|आँख|eye human body part
13_Body_Parts|eyebrow|ଆଖିଭୁଁଇଁ|भौंह|eyebrow human body part
13_Body_Parts|face|ମୁହଁ|चेहरा|face human body part
13_Body_Parts|fingers|ଆଙ୍ଗୁଠି|उंगलियाँ|fingers human body part
13_Body_Parts|foot|ପାଦ|पैर|foot human body part
13_Body_Parts|hand|ହାତ|हाथ|hand human body part
13_Body_Parts|head|ମୁଣ୍ଡ|सिर|head human body part
13_Body_Parts|knee|ଆଣ୍ଠୁ|घुटना|knee human body part
13_Body_Parts|leg|ଗୋଡ଼|टाँग|leg human body part
13_Body_Parts|lip|ଓଠ|होंठ|lip human body part
13_Body_Parts|mouth|ପାଟି|मुँह|mouth human body part
13_Body_Parts|neck|ବେକ|गर्दन|neck human body part
13_Body_Parts|nose|ନାକ|नाक|nose human body part
13_Body_Parts|teeth|ଦାନ୍ତ|दाँत|teeth human body part
13_Body_Parts|toes|ପାଦ ଆଙ୍ଗୁଠି|पैर की उंगलियाँ|human toes foot body part
13_Body_Parts|hair|କେଶ|बाल|hair human body part
13_Body_Parts|forehead|କପାଳ|माथा|forehead human body part
13_Body_Parts|cheek|ଗାଲ|गाल|cheek human body part
13_Body_Parts|chin|ଚିବୁକ|ठोड़ी|chin human body part
13_Body_Parts|tongue|ଜିଭ|जीभ|tongue human body part
13_Body_Parts|throat|ଗଳା|गला|throat human body part
13_Body_Parts|shoulder|କାନ୍ଧ|कंधा|shoulder human body part
13_Body_Parts|chest|ଛାତି|छाती|chest human body part
13_Body_Parts|back|ପିଠି|पीठ|human back body
13_Body_Parts|stomach|ପେଟ|पेट|stomach human body part
13_Body_Parts|waist|କଟି|कमर|waist human body part
13_Body_Parts|thumb|ବୁଢ଼ା ଆଙ୍ଗୁଠି|अंगूठा|thumb human body part
13_Body_Parts|finger|ଆଙ୍ଗୁଠି|उंगली|finger human body part
13_Body_Parts|palm|ତଳହାତ|हथेली|palm human body part
13_Body_Parts|nail|ନଖ|नाखून|fingernail human body part
13_Body_Parts|wrist|ମଣିବନ୍ଧ|कलाई|wrist human body part
13_Body_Parts|ankle|ଗୁଲ୍ଫ|टखना|ankle human body part
13_Body_Parts|heel|ଗୋଇଠି|एड़ी|heel human body part
13_Body_Parts|thigh|ଜଙ୍ଘ|जाँघ|thigh human body part
13_Body_Parts|skin|ଚର୍ମ|त्वचा|skin human body part
13_Body_Parts|heart|ହୃଦୟ|हृदय|human heart organ
13_Body_Parts|brain|ମସ୍ତିଷ୍କ|दिमाग|human brain organ
13_Body_Parts|lungs|ଫୁସଫୁସ|फेफड़े|human lungs organ
13_Body_Parts|bone|ହାଡ଼|हड्डी|human bone
13_Body_Parts|muscle|ମାଂସପେଶୀ|मांसपेशी|human muscle
13_Body_Parts|blood|ରକ୍ତ|खून|blood drop
13_Body_Parts|beard|ଦାଢ଼ି|दाढ़ी|beard human body part
13_Body_Parts|moustache|ଗୁମ୍ଫ|मूँछ|moustache human body part
13_Body_Parts|liver|ଯକୃତ|जिगर|human liver organ
13_Body_Parts|kidney|ବୃକ୍କ|गुर्दा|human kidney organ
13_Body_Parts|ribs|ପଞ୍ଜରା|पसलियाँ|human ribs
13_Body_Parts|navel|ନାଭି|नाभि|navel human body part
13_Body_Parts|jaw|ହନୁ|जबड़ा|jaw human body part
13_Body_Parts|eyelid|ଆଖିପତା|पलक|eyelid human body part
13_Body_Parts|nostril|ନାକ ଛିଦ୍ର|नथुना|nostril human body part
13_Body_Parts|fist|ମୁଠା|मुट्ठी|fist human body part
13_Body_Parts|armpit|କାଖ|बगल|armpit human body part
13_Body_Parts|spine|ମେରୁଦଣ୍ଡ|रीढ़ की हड्डी|human spine
14_Emotions|angry|ରାଗ|गुस्सा|angry emotion child face
14_Emotions|cry|କାନ୍ଦିବା|रोना|cry emotion child face
14_Emotions|excited|ଉତ୍ସାହିତ|उत्साहित|excited emotion child face
14_Emotions|happy|ଖୁସି|खुश|happy emotion child face
14_Emotions|proud|ଗର୍ବିତ|गर्वित|proud emotion child face
14_Emotions|sad|ଦୁଃଖୀ|उदास|sad emotion child face
14_Emotions|scared|ଡରିବା|डरा हुआ|scared emotion child face
14_Emotions|shy|ଲାଜ|शर्मीला|shy emotion child face
14_Emotions|sleepy|ନିଦ୍ରାଳୁ|नींद आना|sleepy emotion child face
14_Emotions|surprised|ଆଶ୍ଚର୍ଯ୍ୟ|आश्चर्यचकित|surprised emotion child face
14_Emotions|love|ପ୍ରେମ|प्यार|love emotion child face
14_Emotions|laughing|ହସିବା|हँसना|laughing emotion child face
14_Emotions|smiling|ମୁରୁକି ହସ|मुस्कुराना|smiling emotion child face
14_Emotions|worried|ଚିନ୍ତିତ|चिंतित|worried emotion child face
14_Emotions|tired|କ୍ଳାନ୍ତ|थका हुआ|tired emotion child face
14_Emotions|hungry|ଭୋକିଲା|भूखा|hungry emotion child face
14_Emotions|thirsty|ଶୋଷିଲା|प्यासा|thirsty emotion child face
14_Emotions|bored|ବିରକ୍ତ|ऊबा हुआ|bored emotion child face
14_Emotions|confused|ଦ୍ୱନ୍ଦ୍ୱରେ|उलझन में|confused emotion child face
14_Emotions|lonely|ଏକୁଟିଆ|अकेला|lonely emotion child face
14_Emotions|jealous|ଈର୍ଷାଳୁ|ईर्ष्यालु|jealous emotion child face
14_Emotions|nervous|ଘାବରା|घबराया हुआ|nervous emotion child face
14_Emotions|brave|ସାହସୀ|बहादुर|brave emotion child face
14_Emotions|kind|ଦୟାଳୁ|दयालु|kind emotion child face
14_Emotions|calm|ଶାନ୍ତ|शांत|calm emotion child face
14_Emotions|sick|ଅସୁସ୍ଥ|बीमार|sick emotion child face
14_Emotions|ashamed|ଲଜ୍ଜିତ|शर्मिंदा|ashamed emotion child face
14_Emotions|disgusted|ଘୃଣା|घृणा|disgusted emotion child face
14_Emotions|grateful|କୃତଜ୍ଞ|आभारी|grateful emotion child face
14_Emotions|curious|କୌତୂହଳୀ|जिज्ञासु|curious emotion child face
14_Emotions|hopeful|ଆଶାବାଦୀ|आशावान|hopeful emotion child face
14_Emotions|cheerful|ଉଲ୍ଲସିତ|प्रसन्न|cheerful emotion child face
14_Emotions|silly|ମଜାଳିଆ|मज़ाकिया|silly emotion child face
14_Emotions|sleeping|ଶୋଇବା|सोना|sleeping emotion child face
14_Emotions|determined|ଦୃଢ଼ ସଂକଳ୍ପ|दृढ़ निश्चयी|determined emotion child face
15_Household|air conditioner|ଏସି|एयर कंडीशनर|air conditioner household
15_Household|bed|ଶଯ୍ୟା|बिस्तर|bed household
15_Household|blender|ବ୍ଲେଣ୍ଡର|ब्लेंडर|blender household
15_Household|ceiling fan|ଛାତ ପଙ୍ଖା|सीलिंग फैन|ceiling fan household
15_Household|pressure cooker|କୁକର|प्रेशर कुकर|pressure cooker kitchen
15_Household|dishwasher|ଡିସୱାସର|डिशवॉशर|dishwasher household
15_Household|dustbin|ଆବର୍ଜନା ଡବା|कूड़ादान|dustbin trash can
15_Household|gas stove|ଗ୍ୟାସ ଚୁଲା|गैस चूल्हा|gas stove household
15_Household|iron|ଇସ୍ତିରି|इस्तरी|clothes iron electric
15_Household|oven|ଓଭେନ|ओवन|oven household
15_Household|refrigerator|ଫ୍ରିଜ|फ्रिज|refrigerator household
15_Household|sewing machine|ସିଲେଇ ମେସିନ|सिलाई मशीन|sewing machine household
15_Household|television|ଟେଲିଭିଜନ|टेलीविजन|television household
15_Household|toaster|ଟୋଷ୍ଟର|टोस्टर|toaster household
15_Household|vacuum cleaner|ଭ୍ୟାକ୍ୟୁମ କ୍ଲିନର|वैक्यूम क्लीनर|vacuum cleaner household
15_Household|washing machine|ଧୋଇବା ମେସିନ|वाशिंग मशीन|washing machine household
15_Household|water purifier|ପାଣି ଫିଲ୍ଟର|वॉटर प्यूरीफायर|water purifier household
15_Household|water heater|ପାଣି ଗରମ କରିବା|वॉटर हीटर|water heater household
15_Household|table|ଟେବୁଲ|मेज़|table household
15_Household|chair|ଚଉକି|कुर्सी|chair household
15_Household|sofa|ସୋଫା|सोफ़ा|sofa household
15_Household|almirah|ଆଲମିରା|अलमारी|almirah household
15_Household|mirror|ଦର୍ପଣ|आईना|mirror household
15_Household|wall clock|କାନ୍ଥ ଘଡ଼ି|दीवार घड़ी|wall clock household
15_Household|light bulb|ବଲ୍ବ|बल्ब|light bulb household
15_Household|door|ଦ୍ୱାର|दरवाज़ा|door household
15_Household|window|ଝରକା|खिड़की|window household
15_Household|broom|ଝାଡ଼ୁ|झाड़ू|broom household
15_Household|bucket|ବାଲଟି|बाल्टी|bucket household
15_Household|mug|ମଗ|मग|mug household
15_Household|plate|ଥାଳି|थाली|plate household
15_Household|spoon|ଚାମଚ|चम्मच|spoon household
15_Household|glass|ଗ୍ଲାସ|गिलास|drinking glass household
15_Household|cup|କପ|कप|cup household
15_Household|bowl|ବାଟି|कटोरी|bowl household
15_Household|knife|ଛୁରୀ|चाकू|kitchen knife
15_Household|fork|କଣ୍ଟା|काँटा|dinner fork
15_Household|pot|ହାଣ୍ଡି|हाँडी|cooking pot kitchen
15_Household|frying pan|କଡ଼ାଇ|कड़ाही|frying pan household
15_Household|kettle|କେଟଲି|केतली|kettle household
15_Household|pillow|ବାଲିସ|तकिया|pillow household
15_Household|blanket|କମ୍ବଳ|कंबल|blanket household
15_Household|mat|ମାଦୁର|चटाई|mat household
15_Household|curtain|ପରଦା|पर्दा|curtain household
15_Household|telephone|ଟେଲିଫୋନ|टेलीफोन|telephone household
15_Household|mobile phone|ମୋବାଇଲ|मोबाइल|mobile phone household
15_Household|torch|ଟର୍ଚ୍ଚ|टॉर्च|torch flashlight
15_Household|umbrella|ଛତା|छाता|umbrella household
15_Household|lock|ତାଲା|ताला|padlock
15_Household|key|ଚାବି|चाबी|door key
15_Household|soap|ସାବୁନ|साबुन|soap household
15_Household|towel|ତଉଲିଆ|तौलिया|towel household
15_Household|comb|କଂଘେଇ|कंघी|comb household
15_Household|toothbrush|ଦାନ୍ତ ବ୍ରଶ|टूथब्रश|toothbrush household
15_Household|scissors|କଞ୍ଚି|कैंची|scissors household
15_Household|hammer|ହାତୁଡ଼ି|हथौड़ा|hammer household
15_Household|ladder|ସିଢ଼ି|सीढ़ी|ladder household
15_Household|tap|ନଳ|नल|water tap
15_Household|table fan|ଟେବୁଲ ପଙ୍ଖା|टेबल फैन|table fan household
15_Household|lantern|ଲଣ୍ଠନ|लालटेन|lantern household
15_Household|candle|ମହମବତୀ|मोमबत्ती|candle household
15_Household|matchbox|ଦିଆସିଲି|माचिस|matchbox household
15_Household|mixer grinder|ମିକ୍ସର|मिक्सर ग्राइंडर|mixer grinder household
15_Household|grinding stone|ଶିଲପୁଆ|सिलबट्टा|grinding stone sil batta
15_Household|bookshelf|ବହି ଆଲମାରୀ|किताबों की अलमारी|bookshelf household
15_Household|hanger|ହ୍ୟାଙ୍ଗର|हैंगर|clothes hanger
15_Household|inverter|ଇନଭର୍ଟର|इन्वर्टर|home inverter
15_Household|switch board|ସ୍ୱିଚ ବୋର୍ଡ|स्विच बोर्ड|electric switch board
15_Household|cot|ଖଟ|खाट|cot bed
15_Household|stool|ଷ୍ଟୁଲ|स्टूल|stool seat
15_Household|diya lamp|ଦୀପ|दीया|diya oil lamp
15_Household|photo frame|ଫଟୋ ଫ୍ରେମ|फोटो फ्रेम|photo frame household
15_Household|flower vase|ଫୁଲଦାନୀ|फूलदान|flower vase household
15_Household|dining table|ଖାଇବା ଟେବୁଲ|खाने की मेज़|dining table household
16_Transport|aeroplane|ବିମାନ|हवाई जहाज|aeroplane airplane flying
16_Transport|ambulance|ଆମ୍ବୁଲାନ୍ସ|एम्बुलेंस|ambulance vehicle
16_Transport|auto rickshaw|ଅଟୋ|ऑटो रिक्शा|auto rickshaw india
16_Transport|bicycle|ସାଇକେଲ|साइकिल|bicycle vehicle
16_Transport|bullock cart|ବଳଦ ଗାଡ଼ି|बैलगाड़ी|bullock cart india
16_Transport|bus|ବସ|बस|bus vehicle
16_Transport|car|କାର|कार|car vehicle
16_Transport|fighter plane|ଯୁଦ୍ଧ ବିମାନ|लड़ाकू विमान|fighter jet
16_Transport|helicopter|ହେଲିକପ୍ଟର|हेलीकॉप्टर|helicopter vehicle
16_Transport|JCB|ଜେସିବି|जेसीबी|JCB excavator
16_Transport|jeep|ଜିପ|जीप|jeep vehicle
16_Transport|rocket|ରକେଟ|रॉकेट|rocket vehicle
16_Transport|scooter|ସ୍କୁଟର|स्कूटर|scooter vehicle
16_Transport|ship|ଜାହାଜ|जहाज|ship vehicle
16_Transport|space shuttle|ସ୍ପେସ ସଟଲ|स्पेस शटल|space shuttle vehicle
16_Transport|submarine|ଜଳଯାନ|पनडुब्बी|submarine vehicle
16_Transport|tank|ଟ୍ୟାଙ୍କ|टैंक|army battle tank
16_Transport|tractor|ଟ୍ରାକ୍ଟର|ट्रैक्टर|tractor vehicle
16_Transport|train|ଟ୍ରେନ|रेलगाड़ी|train vehicle
16_Transport|truck|ଟ୍ରକ|ट्रक|truck vehicle
16_Transport|water scooter|ୱାଟର ସ୍କୁଟର|वॉटर स्कूटर|jet ski water scooter
16_Transport|motorcycle|ମୋଟରସାଇକେଲ|मोटरसाइकिल|motorcycle vehicle
16_Transport|cycle rickshaw|ସାଇକେଲ ରିକ୍ସା|साइकिल रिक्शा|cycle rickshaw vehicle
16_Transport|taxi|ଟ୍ୟାକ୍ସି|टैक्सी|taxi vehicle
16_Transport|van|ଭ୍ୟାନ|वैन|van vehicle
16_Transport|metro train|ମେଟ୍ରୋ ଟ୍ରେନ|मेट्रो ट्रेन|metro train vehicle
16_Transport|boat|ଡଙ୍ଗା|नाव|boat vehicle
16_Transport|cruise ship|କ୍ରୁଜ ଜାହାଜ|क्रूज़ जहाज़|cruise ship vehicle
16_Transport|tram|ଟ୍ରାମ|ट्राम|tram vehicle
16_Transport|fire engine|ଅଗ୍ନିଶମ ଗାଡ଼ି|दमकल गाड़ी|fire engine vehicle
16_Transport|police car|ପୋଲିସ ଗାଡ଼ି|पुलिस की गाड़ी|police car vehicle
16_Transport|school bus|ସ୍କୁଲ ବସ|स्कूल बस|school bus vehicle
16_Transport|horse cart|ଘୋଡ଼ା ଗାଡ଼ି|तांगा|horse cart tanga india
16_Transport|hot air balloon|ଗରମ ବାୟୁ ବେଲୁନ|गर्म हवा का गुब्बारा|hot air balloon vehicle
16_Transport|cable car|କେବୁଲ କାର|केबल कार|cable car vehicle
16_Transport|bullet train|ବୁଲେଟ ଟ୍ରେନ|बुलेट ट्रेन|bullet train vehicle
16_Transport|crane|କ୍ରେନ|क्रेन|construction crane vehicle
16_Transport|bulldozer|ବୁଲଡୋଜର|बुलडोज़र|bulldozer vehicle
16_Transport|road roller|ରୋଡ ରୋଲର|रोड रोलर|road roller vehicle
16_Transport|dump truck|ଡମ୍ପର ଟ୍ରକ|डंपर ट्रक|dump truck vehicle
16_Transport|ferry|ଫେରି|फेरी|ferry boat
16_Transport|speed boat|ସ୍ପିଡବୋଟ|स्पीडबोट|speed boat vehicle
16_Transport|sailing boat|ପାଲ ଡଙ୍ଗା|पाल वाली नाव|sailing boat
16_Transport|jet plane|ଜେଟ ବିମାନ|जेट विमान|passenger jet plane
16_Transport|wheelchair|ହ୍ୱିଲଚେୟାର|व्हीलचेयर|wheelchair vehicle
16_Transport|handcart|ଠେଲା ଗାଡ଼ି|ठेला|handcart india
16_Transport|tanker truck|ଟ୍ୟାଙ୍କର|टैंकर|tanker truck
16_Transport|electric car|ଇଲେକ୍ଟ୍ରିକ କାର|इलेक्ट्रिक कार|electric car charging
16_Transport|e-rickshaw|ଇ-ରିକ୍ସା|ई-रिक्शा|e rickshaw india
16_Transport|steam engine|ବାଷ୍ପ ଇଞ୍ଜିନ|भाप इंजन|steam engine train
16_Transport|tempo|ଟେମ୍ପୋ|टेम्पो|tempo vehicle india
16_Transport|kayak|କାୟାକ|कयाक|kayak boat
16_Transport|lifeboat|ଜୀବନ ରକ୍ଷା ଡଙ୍ଗା|लाइफबोट|lifeboat
17_Professions|barber|ନାଇ|नाई|barber profession
17_Professions|builder|ନିର୍ମାତା|बिल्डर|construction worker builder
17_Professions|doctor|ଡାକ୍ତର|डॉक्टर|doctor profession
17_Professions|electrician|ବିଦ୍ୟୁତ କାରିଗର|इलेक्ट्रीशियन|electrician profession
17_Professions|farmer|ଚାଷୀ|किसान|farmer profession
17_Professions|magician|ଯାଦୁଗର|जादूगर|magician profession
17_Professions|nurse|ନର୍ସ|नर्स|nurse profession
17_Professions|painter|ଚିତ୍ରକର|पेंटर|house wall painter
17_Professions|photographer|ଫଟୋଗ୍ରାଫର|फोटोग्राफर|photographer profession
17_Professions|pilot|ପାଇଲଟ|पायलट|pilot profession
17_Professions|police|ପୋଲିସ|पुलिस|police officer
17_Professions|postman|ଡାକିଆ|पोस्टमैन|postman profession
17_Professions|potter|କୁମ୍ଭାର|कुम्हार|potter making clay pot
17_Professions|scientist|ବୈଜ୍ଞାନିକ|वैज्ञानिक|scientist laboratory
17_Professions|singer|ଗାୟକ|गायक|singer profession
17_Professions|soldier|ସୈନିକ|सैनिक|soldier profession
17_Professions|tailor|ଦରଜି|दर्जी|tailor profession
17_Professions|teacher|ଶିକ୍ଷକ|शिक्षक|teacher profession
17_Professions|waiter|ୱେଟର|वेटर|waiter profession
17_Professions|engineer|ଇଞ୍ଜିନିୟର|इंजीनियर|engineer profession
17_Professions|lawyer|ଓକିଲ|वकील|lawyer profession
17_Professions|judge|ବିଚାରପତି|न्यायाधीश|judge profession
17_Professions|driver|ଡ୍ରାଇଭର|ड्राइवर|driver car profession
17_Professions|cook|ରୋଷେୟା|रसोइया|cook chef kitchen
17_Professions|baker|ବେକର|बेकर|baker bakery profession
17_Professions|fisherman|ମାଛୁଆ|मछुआरा|fisherman profession
17_Professions|carpenter|ବଢ଼େଇ|बढ़ई|carpenter profession
17_Professions|blacksmith|କମାର|लोहार|blacksmith profession
17_Professions|goldsmith|ସୁନାର|सुनार|goldsmith jeweller
17_Professions|mason|ରାଜମିସ୍ତ୍ରୀ|राजमिस्त्री|mason bricklayer
17_Professions|plumber|ପ୍ଲମ୍ବର|प्लंबर|plumber profession
17_Professions|mechanic|ମେକାନିକ|मैकेनिक|mechanic profession
17_Professions|shopkeeper|ଦୋକାନୀ|दुकानदार|shopkeeper profession
17_Professions|vegetable seller|ପରିବା ବିକ୍ରେତା|सब्ज़ीवाला|vegetable seller india
17_Professions|milkman|ଦୁଧ ବିକ୍ରେତା|दूधवाला|milkman india
17_Professions|cobbler|ମୋଚି|मोची|cobbler shoe repair
17_Professions|weaver|ତନ୍ତୀ|बुनकर|weaver handloom
17_Professions|washerman|ଧୋବା|धोबी|washerman dhobi india
17_Professions|gardener|ମାଳୀ|माली|gardener profession
17_Professions|firefighter|ଅଗ୍ନିଶମ କର୍ମୀ|दमकलकर्मी|firefighter profession
17_Professions|astronaut|ମହାକାଶଚାରୀ|अंतरिक्ष यात्री|astronaut profession
17_Professions|dentist|ଦନ୍ତ ଚିକିତ୍ସକ|दंत चिकित्सक|dentist profession
17_Professions|veterinarian|ପଶୁ ଚିକିତ୍ସକ|पशु चिकित्सक|veterinarian profession
17_Professions|journalist|ସାମ୍ବାଦିକ|पत्रकार|journalist profession
17_Professions|artist|କଳାକାର|कलाकार|artist profession
17_Professions|dancer|ନର୍ତ୍ତକ|नर्तक|dancer profession
17_Professions|musician|ସଙ୍ଗୀତଜ୍ଞ|संगीतकार|musician profession
17_Professions|actor|ଅଭିନେତା|अभिनेता|actor profession
17_Professions|sportsman|ଖେଳାଳି|खिलाड़ी|sportsman athlete
17_Professions|bank clerk|ବ୍ୟାଙ୍କ କର୍ମଚାରୀ|बैंक कर्मचारी|bank clerk profession
17_Professions|security guard|ପ୍ରହରୀ|चौकीदार|security guard profession
17_Professions|shepherd|ମେଷପାଳକ|चरवाहा|shepherd profession
17_Professions|priest|ପୂଜାରୀ|पुजारी|priest pandit india
17_Professions|professor|ପ୍ରାଧ୍ୟାପକ|प्रोफेसर|professor profession
17_Professions|pharmacist|ଔଷଧ ବିକ୍ରେତା|दवा विक्रेता|pharmacist medical shop
17_Professions|architect|ସ୍ଥପତି|वास्तुकार|architect profession
17_Professions|writer|ଲେଖକ|लेखक|writer author
17_Professions|bus conductor|କଣ୍ଡକ୍ଟର|कंडक्टर|bus conductor
17_Professions|chef|ଶେଫ|शेफ|chef profession
17_Professions|cleaner|ସଫେଇ କର୍ମୀ|सफाईकर्मी|street cleaner sweeper
17_Professions|coach|ପ୍ରଶିକ୍ଷକ|प्रशिक्षक|sports coach
17_Professions|cameraman|କ୍ୟାମେରାମ୍ୟାନ|कैमरामैन|cameraman profession
17_Professions|tea seller|ଚା ବିକ୍ରେତା|चायवाला|tea seller chaiwala india
17_Professions|ice cream seller|ଆଇସକ୍ରିମ ବିକ୍ରେତା|आइसक्रीम वाला|ice cream seller profession
25_Computers|CPU|ସିପିୟୁ|सीपीयू|computer cpu cabinet
25_Computers|headphone|ହେଡଫୋନ|हेडफोन|headphone computer
25_Computers|keyboard|କିବୋର୍ଡ|कीबोर्ड|keyboard computer
25_Computers|monitor|ମନିଟର|मॉनिटर|monitor computer
25_Computers|mouse|ମାଉସ|माउस|computer mouse
25_Computers|pen drive|ପେନ ଡ୍ରାଇଭ|पेन ड्राइव|usb pen drive
25_Computers|printer|ପ୍ରିଣ୍ଟର|प्रिंटर|printer computer
25_Computers|scanner|ସ୍କାନର|स्कैनर|scanner computer
25_Computers|speakers|ସ୍ପିକର|स्पीकर|computer speakers
25_Computers|UPS|ୟୁପିଏସ|यूपीएस|UPS uninterruptible power supply for computer
25_Computers|web camera|ୱେବ କ୍ୟାମେରା|वेब कैमरा|webcam
25_Computers|laptop|ଲାପଟପ|लैपटॉप|laptop computer
25_Computers|desktop computer|ଡେସ୍କଟପ କମ୍ପ୍ୟୁଟର|डेस्कटॉप कंप्यूटर|desktop computer computer
25_Computers|tablet|ଟାବଲେଟ|टैबलेट|tablet computer
25_Computers|smartphone|ସ୍ମାର୍ଟଫୋନ|स्मार्टफोन|smartphone computer
25_Computers|microphone|ମାଇକ୍ରୋଫୋନ|माइक्रोफोन|microphone computer
25_Computers|router|ରାଉଟର|राउटर|wifi router
25_Computers|modem|ମଡେମ|मॉडेम|internet modem
25_Computers|hard disk|ହାର୍ଡ ଡିସ୍କ|हार्ड डिस्क|computer hard disk
25_Computers|CD|ସିଡି|सीडी|compact disc cd
25_Computers|memory card|ମେମୋରୀ କାର୍ଡ|मेमोरी कार्ड|sd memory card
25_Computers|projector|ପ୍ରୋଜେକ୍ଟର|प्रोजेक्टर|projector computer
25_Computers|joystick|ଜୟଷ୍ଟିକ|जॉयस्टिक|joystick game
25_Computers|mouse pad|ମାଉସ ପ୍ୟାଡ|माउस पैड|mouse pad computer
25_Computers|USB cable|ୟୁଏସବି କେବୁଲ|यूएसबी केबल|usb cable
25_Computers|charger|ଚାର୍ଜର|चार्जर|mobile charger
25_Computers|power bank|ପାୱାର ବ୍ୟାଙ୍କ|पावर बैंक|power bank computer
25_Computers|motherboard|ମଦରବୋର୍ଡ|मदरबोर्ड|computer motherboard
25_Computers|RAM|ରାମ|रैम|RAM memory module computer
25_Computers|smart watch|ସ୍ମାର୍ଟ ୱାଚ|स्मार्ट वॉच|smart watch computer
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
28_Countries|Afghanistan|ଆଫଗାନିସ୍ତାନ|अफ़ग़ानिस्तान|Afghanistan country flag map
28_Countries|Australia|ଅଷ୍ଟ୍ରେଲିଆ|ऑस्ट्रेलिया|Australia country flag map
28_Countries|Bangladesh|ବାଂଲାଦେଶ|बांग्लादेश|Bangladesh country flag map
28_Countries|Bhutan|ଭୁଟାନ|भूटान|Bhutan country flag map
28_Countries|Brazil|ବ୍ରାଜିଲ|ब्राज़ील|Brazil country flag map
28_Countries|Canada|କାନାଡା|कनाडा|Canada country flag map
28_Countries|China|ଚୀନ|चीन|China country flag map
28_Countries|France|ଫ୍ରାନ୍ସ|फ़्रांस|France country flag map
28_Countries|Germany|ଜର୍ମାନୀ|जर्मनी|Germany country flag map
28_Countries|India|ଭାରତ|भारत|India country flag map
28_Countries|Iran|ଇରାନ|ईरान|Iran country flag map
28_Countries|Italy|ଇଟାଲୀ|इटली|Italy country flag map
28_Countries|Kenya|କେନିଆ|केन्या|Kenya country flag map
28_Countries|Malaysia|ମାଲେସିଆ|मलेशिया|Malaysia country flag map
28_Countries|Myanmar|ମିଆଁମାର|म्यांमार|Myanmar country flag map
28_Countries|Nepal|ନେପାଳ|नेपाल|Nepal country flag map
28_Countries|Pakistan|ପାକିସ୍ତାନ|पाकिस्तान|Pakistan country flag map
28_Countries|Russia|ରୁଷିଆ|रूस|Russia country flag map
28_Countries|South Africa|ଦକ୍ଷିଣ ଆଫ୍ରିକା|दक्षिण अफ्रीका|South Africa country flag map
28_Countries|Sri Lanka|ଶ୍ରୀଲଙ୍କା|श्रीलंका|Sri Lanka country flag map
28_Countries|Turkey|ତୁର୍କୀ|तुर्की|Turkey country flag map
28_Countries|USA|ଆମେରିକା|अमेरिका|United States of America flag map
28_Countries|Japan|ଜାପାନ|जापान|Japan country flag map
28_Countries|South Korea|ଦକ୍ଷିଣ କୋରିଆ|दक्षिण कोरिया|South Korea country flag map
28_Countries|Indonesia|ଇଣ୍ଡୋନେସିଆ|इंडोनेशिया|Indonesia country flag map
28_Countries|Thailand|ଥାଇଲାଣ୍ଡ|थाईलैंड|Thailand country flag map
28_Countries|Vietnam|ଭିଏତନାମ|वियतनाम|Vietnam country flag map
28_Countries|Singapore|ସିଙ୍ଗାପୁର|सिंगापुर|Singapore country flag map
28_Countries|Philippines|ଫିଲିପାଇନ୍ସ|फिलीपींस|Philippines country flag map
28_Countries|Maldives|ମାଲଦ୍ୱୀପ|मालदीव|Maldives country flag map
28_Countries|Saudi Arabia|ସାଉଦି ଆରବ|सऊदी अरब|Saudi Arabia country flag map
28_Countries|UAE|ସଂଯୁକ୍ତ ଆରବ ଏମିରେଟ୍ସ|संयुक्त अरब अमीरात|United Arab Emirates flag map
28_Countries|Iraq|ଇରାକ|इराक|Iraq country flag map
28_Countries|Israel|ଇସ୍ରାଏଲ|इज़राइल|Israel country flag map
28_Countries|Egypt|ମିଶର|मिस्र|Egypt country flag map
28_Countries|Nigeria|ନାଇଜେରିଆ|नाइजीरिया|Nigeria country flag map
28_Countries|Ethiopia|ଇଥିଓପିଆ|इथियोपिया|Ethiopia country flag map
28_Countries|Ghana|ଘାନା|घाना|Ghana country flag map
28_Countries|Morocco|ମୋରୋକ୍କୋ|मोरक्को|Morocco country flag map
28_Countries|United Kingdom|ଯୁକ୍ତରାଜ୍ୟ|यूनाइटेड किंगडम|United Kingdom flag map
28_Countries|Ireland|ଆୟର୍ଲ୍ୟାଣ୍ଡ|आयरलैंड|Ireland country flag map
28_Countries|Spain|ସ୍ପେନ|स्पेन|Spain country flag map
28_Countries|Portugal|ପର୍ତ୍ତୁଗାଲ|पुर्तगाल|Portugal country flag map
28_Countries|Netherlands|ନେଦରଲ୍ୟାଣ୍ଡ|नीदरलैंड|Netherlands country flag map
28_Countries|Switzerland|ସ୍ୱିଜରଲ୍ୟାଣ୍ଡ|स्विट्ज़रलैंड|Switzerland country flag map
28_Countries|Sweden|ସ୍ୱିଡେନ|स्वीडन|Sweden country flag map
28_Countries|Norway|ନରୱେ|नॉर्वे|Norway country flag map
28_Countries|Denmark|ଡେନମାର୍କ|डेनमार्क|Denmark country flag map
28_Countries|Finland|ଫିନଲ୍ୟାଣ୍ଡ|फ़िनलैंड|Finland country flag map
28_Countries|Greece|ଗ୍ରୀସ|यूनान|Greece country flag map
28_Countries|Poland|ପୋଲାଣ୍ଡ|पोलैंड|Poland country flag map
28_Countries|Ukraine|ୟୁକ୍ରେନ|यूक्रेन|Ukraine country flag map
28_Countries|Mexico|ମେକ୍ସିକୋ|मेक्सिको|Mexico country flag map
28_Countries|Argentina|ଆର୍ଜେଣ୍ଟିନା|अर्जेंटीना|Argentina country flag map
28_Countries|Cuba|କ୍ୟୁବା|क्यूबा|Cuba country flag map
28_Countries|Peru|ପେରୁ|पेरू|Peru country flag map
28_Countries|Chile|ଚିଲି|चिली|Chile country flag map
28_Countries|New Zealand|ନିଉଜିଲ୍ୟାଣ୍ଡ|न्यूज़ीलैंड|New Zealand country flag map
28_Countries|Mongolia|ମଙ୍ଗୋଲିଆ|मंगोलिया|Mongolia country flag map
28_Countries|Kazakhstan|କାଜାକସ୍ତାନ|कज़ाखस्तान|Kazakhstan country flag map
28_Countries|Tanzania|ତାନଜାନିଆ|तंज़ानिया|Tanzania country flag map
28_Countries|Kuwait|କୁଏତ|कुवैत|Kuwait country flag map
28_Countries|Qatar|କତାର|क़तर|Qatar country flag map
28_Countries|Oman|ଓମାନ|ओमान|Oman country flag map
29_Science_and_Space|A P J Abdul Kalam|ଏପିଜେ ଅବଦୁଲ କଲାମ|एपीजे अब्दुल कलाम|APJ Abdul Kalam
29_Science_and_Space|Aryabhata|ଆର୍ଯ୍ୟଭଟ୍ଟ|आर्यभट्ट|Aryabhata mathematician
29_Science_and_Space|asteroid|କ୍ଷୁଦ୍ରଗ୍ରହ|क्षुद्रग्रह|asteroid in space
29_Science_and_Space|Subhas Chandra Bose|ସୁଭାଷ ଚନ୍ଦ୍ର ବୋଷ|सुभाष चंद्र बोस|Netaji Subhas Chandra Bose
29_Science_and_Space|comet|ଧୂମକେତୁ|धूमकेतु|comet in space
29_Science_and_Space|Marie Curie|ମେରି କ୍ୟୁରି|मैरी क्यूरी|Marie Curie science
29_Science_and_Space|C V Raman|ସି ଭି ରମଣ|सी वी रमन|C V Raman scientist
29_Science_and_Space|Charles Darwin|ଚାର୍ଲ୍ସ ଡାରୱିନ|चार्ल्स डार्विन|Charles Darwin science
29_Science_and_Space|Earth|ପୃଥିବୀ|पृथ्वी|planet earth from space
29_Science_and_Space|Albert Einstein|ଆଲବର୍ଟ ଆଇନଷ୍ଟାଇନ|अल्बर्ट आइंस्टीन|Albert Einstein science
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
29_Science_and_Space|pole star|ଧ୍ରୁବତାରା|ध्रुव तारा|pole star north star"""
WORDS = [tuple(l.split("|", 4)) for l in DATA.strip().split("\n")]   # (chapter, english, odia, hindi, search words)

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"]

def http(url, timeout=12, maxb=6 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": random.choice(UAS), "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close", "Cache-Control": "no-cache",
        "Cookie": "CONSENT=YES+cb; SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"})
    with urllib.request.build_opener().open(req, timeout=timeout) as r:
        data = r.read(maxb + 1)
        if len(data) > maxb: raise ValueError("too big")
        return data, r.headers.get("Content-Type", "")

# ---------------- search: Google Images (PNG filter) first, Bing (transparent filter) as fallback ----------------
SEARCH_SEM = threading.Semaphore(SEARCH_PARALLEL)
G_FAIL = [0]                                   # consecutive Google failures; after 8 Google is skipped (blocked)
BAD_HOSTS = ("gstatic.com", "google.com", "googleusercontent.com", "ggpht.com", "youtube.com")

def google_urls(q, png):
    if G_FAIL[0] >= 8: return []
    params = {"q": q, "udm": "2", "hl": "en", "safe": "active"}     # udm=2 = Images tab, same as the screenshot
    if png: params["tbs"] = "ift:png"                               # = the "type:png" filter
    try:
        with SEARCH_SEM:
            time.sleep(random.random() * 0.8)
            page, _ = http("https://www.google.com/search?" + urllib.parse.urlencode(params), timeout=15, maxb=4 * 1024 * 1024)
    except Exception:
        G_FAIL[0] += 1; return []
    page = page.decode("utf-8", "ignore"); out = []
    if "unusual traffic" in page or "/sorry/" in page:
        G_FAIL[0] += 1; return []
    for m in re.finditer(r'\["(https?:[^"\s]+?)",\s*(\d{2,5}),\s*(\d{2,5})\]', page):
        try: u = json.loads('"' + m.group(1) + '"')
        except Exception: u = m.group(1).replace("\\/", "/").replace("\\u003d", "=").replace("\\u0026", "&")
        if any(h in u for h in BAD_HOSTS): continue                # thumbnails / google pages
        if min(int(m.group(2)), int(m.group(3))) < MIN_SIDE: continue
        if u not in out: out.append(u)
        if len(out) >= CANDIDATES + 10: break
    G_FAIL[0] = 0 if out else G_FAIL[0] + 1
    return out

def bing_urls(q, folder, png, first=1):
    if png: flt = "&qft=" + urllib.parse.quote("+filterui:photo-transparent")
    elif any(k in folder.lower() for k in PHOTO_CHAPTERS): flt = "&qft=" + urllib.parse.quote("+filterui:photo-photo")
    else: flt = ""
    with SEARCH_SEM:
        page, _ = http("https://www.bing.com/images/search?adlt=strict&form=HDRSC3&first=" + str(first) + "&count=50&cvid="
                       + uuid.uuid4().hex.upper() + flt + "&q=" + urllib.parse.quote(q))
    page = page.decode("utf-8", "ignore"); out = []
    for m in re.finditer(r'murl(?:&quot;|")\s*:\s*(?:&quot;|")(https?:[^"<>\s]+?)(?:&quot;|")', page):
        u = (m.group(1).replace("&amp;", "&").replace("\\u0026", "&").replace("\\u003d", "=")
             .replace("\\u003f", "?").replace("\\/", "/"))
        if u not in out: out.append(u)
        if len(out) >= CANDIDATES + 10: break
    return out

def search_urls(q, folder, png, first=1):
    urls = google_urls(q, png)
    if len(urls) < 8:                                           # Google blocked / too few -> add Bing results
        for u in bing_urls(q, folder, png, first):
            if u not in urls: urls.append(u)
    return urls

# ---------------- pictures ----------------
def flat(im):
    """RGBA -> RGB on white (used for the checker and the duplicate test)"""
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); return bg
    return im.convert("RGB")

def fetch_picture(url):
    """one candidate -> PIL image (RGB, or RGBA if it has a real transparent background, max 600 px) or None"""
    try:
        data, ctype = http(url)
        if ctype and not ctype.lower().startswith("image/"): return None
        im = Image.open(io.BytesIO(data)); im.load()
        if min(im.size) < MIN_SIDE: return None
        if max(im.size) / float(min(im.size)) > 3: return None          # banners / strips
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        if has_alpha:
            im = im.convert("RGBA")
            if im.split()[-1].getextrema()[0] > 250: im = im.convert("RGB")   # alpha channel exists but is fully opaque
        else:
            im = im.convert("RGB")
        im.thumbnail((600, 600))
        return im
    except Exception:
        return None

def ahash(im):
    g = flat(im).convert("L").resize((8, 8)); px = list(g.tobytes()); avg = sum(px) / 64.0
    return sum(1 << i for i, v in enumerate(px) if v > avg)

def same(a, b):
    return bin(a ^ b).count("1") <= 4

# (search words, png filter on/off): the first ones copy the screenshot search "<word> type:png"
VAR = [("{q}", True), ("{q} png transparent background", True), ("{en}", True), ("{q} isolated white background", False),
       ("{q} hd", True), ("{q}", False), ("single {q} cutout", True), ("{q} close up", False)]
def variants(w, rnd):
    t, png = VAR[rnd % len(VAR)]
    return t.format(q=w.q, en=w.en), png

# ---------------- word state ----------------
class W:
    def __init__(s, i, item, ci):
        s.i, s.ci = i, ci
        s.chapter, s.en, s.od, s.hi, s.q = item
        s.dir = os.path.join(CACHE, str(i))
        s.seen, s.hash, s.new, s.cands, s.count = set(), {}, [], [], 0     # cands: (probability, rank, path)
        s.picked, s.n_good, s.conf, s.verified, s.err, s.rounds = [], 0, 0.0, False, "", 0

shutil.rmtree(CACHE, ignore_errors=True); os.makedirs(CACHE, exist_ok=True)
chapters = {}
for it in WORDS: chapters.setdefault(it[0], []).append(it)
words = []
for ch in sorted(chapters):
    for ci, it in enumerate(chapters[ch]): words.append(W(len(words), it, ci))
for w in words: os.makedirs(w.dir, exist_ok=True)
print("Words: %d in %d chapters" % (len(words), len(chapters)))

img_pool = ThreadPoolExecutor(IMG_WORKERS)

def download_word(w, rnd):
    """one download round of ONE word; candidates are written to disk (PNG if transparent, else JPEG)"""
    w.rounds = rnd + 1
    q, png = variants(w, rnd)
    urls, err = [], ""
    for attempt in range(3):
        try:
            urls = search_urls(q, w.chapter, png, first=1 + 35 * (rnd % 3))
            if urls: break
            err = "no results"
        except Exception as e:
            err = str(e)
        time.sleep(1.5 * (attempt + 1) + random.random())
    urls = [u for u in urls if u not in w.seen]
    if not urls:
        w.err = "search: " + err; return
    w.seen.update(urls)
    got = 0
    for im in img_pool.map(fetch_picture, urls[:CANDIDATES + 10]):
        if im is None: continue
        h = ahash(im)
        if any(same(h, o) for o in w.hash.values()): continue          # no duplicates
        if im.mode == "RGBA":
            path = os.path.join(w.dir, "%d.png" % w.count); im.save(path, "PNG")
        else:
            path = os.path.join(w.dir, "%d.jpg" % w.count); im.save(path, "JPEG", quality=88)
        w.count += 1; w.hash[path] = h; w.new.append(path); got += 1
        if got >= CANDIDATES: break
    w.err = "" if (got or w.cands) else "no usable picture"

def download_round(ws, rnd, label):
    done, t = 0, time.time()
    with ThreadPoolExecutor(WORD_WORKERS) as wp:
        futs = [wp.submit(download_word, w, rnd) for w in ws]
        for f in as_completed(futs):
            try: f.result()
            except Exception as e: print("   error:", e)
            done += 1
            if done % 100 == 0 or done == len(ws):
                print("   %s: %d/%d words downloaded  [%.0f s]  (google %s)" % (label, done, len(ws), time.time() - t,
                      "blocked -> using Bing" if G_FAIL[0] >= 8 else "ok"))

# ---------------- the checker (CLIP) ----------------
dev = "cuda" if torch.cuda.is_available() else "cpu"
print("Checker running on:", dev)
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(dev).eval()
proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

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

TXT = {ch: text_feats(["a photo of " + it[4] for it in items]) for ch, items in chapters.items()}

def load_rgb(path):
    try:
        im = Image.open(path); im.load(); return flat(im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im)
    except Exception:
        return None

def choose(w):
    """4 best pictures of the word. GOOD = word is in the checker's top 3 of its chapter, or probability >= 0.15"""
    order = sorted(w.cands, key=lambda c: -c[0])
    good = [c for c in order if c[1] < 3 or c[0] >= 0.15]
    rest = [c for c in order if c not in good]
    pick = (good + rest)[:GRID]
    w.picked = [c[2] for c in pick]
    w.n_good = len([c for c in pick if c in good])
    w.conf = sum(c[0] for c in pick) / max(1, len(pick))
    w.verified = w.n_good >= 3

def verify(ws, label):
    """verify ALL new pictures of ALL given words at once (GPU/CPU batches)"""
    pairs = [(w, p) for w in ws for p in w.new]
    by_ch = {}
    for w, p in pairs: by_ch.setdefault(w.chapter, []).append((w, p))
    done, t = 0, time.time()
    for ch, lst in by_ch.items():
        for s in range(0, len(lst), BATCH):
            chunk = lst[s:s + BATCH]
            imgs = list(img_pool.map(load_rgb, [p for _, p in chunk]))
            ok = [(w, p, im) for (w, p), im in zip(chunk, imgs) if im is not None]
            done += len(chunk)
            if not ok: continue
            with torch.no_grad():
                probs = (100.0 * image_feats([im for _, _, im in ok]) @ TXT[ch].T).softmax(dim=-1).cpu()
            for row, (w, p, _) in enumerate(ok):
                pr = probs[row]; v = float(pr[w.ci]); rank = int((pr > pr[w.ci]).sum())
                w.cands.append((v, rank, p))
        print("   %s: verified %d/%d pictures  [%.0f s]" % (label, done, len(pairs), time.time() - t))
    for w in ws:
        w.new = []
        if w.cands: choose(w)

# ================================ RUN: search + download + verify + retry ================================
t0 = time.time()
print("\n=== PHASE 1: downloading ALL %d words of ALL chapters at once ..." % len(words))
download_round(words, 0, "download")
print("\n=== PHASE 2: verifying ALL pictures at once ...")
verify(words, "verify")

rnd = 0
while True:
    pending = [w for w in words if not w.verified]
    print("\n=== verified %d/%d words" % (len(words) - len(pending), len(words)))
    if rnd >= MAX_ROUNDS:                                       # after MAX_ROUNDS only words WITHOUT any picture go on
        pending = [w for w in pending if not w.cands]
    if not pending or rnd >= MAX_ROUNDS + NOIMG_EXTRA: break
    rnd += 1
    names = ", ".join(w.en for w in pending[:8]) + (" ..." if len(pending) > 8 else "")
    print("=== RETRY round %d: downloading ONLY the %d unverified words again: %s" % (rnd, len(pending), names))
    download_round(pending, rnd, "retry %d" % rnd)
    verify(pending, "retry %d" % rnd)

# ================================ PHASE 4: remove background -> white background -> merge 4 ================================
print("\n=== PHASE 4: removing backgrounds, white background, merging 4 pictures per word ...")
from rembg import remove, new_session
SESSION = new_session(REMBG_MODEL)                              # model is downloaded once (~170 MB for u2net)

def to_tile(im_rgba_or_rgb, use_alpha):
    """crop to the subject, fit into a TILE x TILE white square"""
    if use_alpha:
        a = im_rgba_or_rgb.split()[-1]
        bbox = a.point(lambda v: 255 if v > 20 else 0).getbbox()
        if bbox is None: return None
        w0, h0 = im_rgba_or_rgb.size
        if (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 0.03 * w0 * h0: return None   # nothing / noise left -> use original
        im = im_rgba_or_rgb.crop(bbox)
    else:
        im = im_rgba_or_rgb
    scale = (TILE * (0.92 if use_alpha else 1.0)) / float(max(im.size))
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    tile = Image.new("RGB", (TILE, TILE), (255, 255, 255))
    pos = ((TILE - im.width) // 2, (TILE - im.height) // 2)
    if use_alpha: tile.paste(im, pos, mask=im.split()[-1])
    else: tile.paste(im.convert("RGB"), pos)
    return tile

def cutout(path):
    """one picture -> TILE x TILE picture: background removed, on white. Already-transparent PNGs skip the AI."""
    try:
        im = Image.open(path); im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            a = im.split()[-1]; hist = a.histogram()
            if sum(hist[:250]) > 0.05 * im.width * im.height:    # real transparent background -> no AI needed
                t = to_tile(im, True)
                if t is not None: return t
            im = flat(im)
        else:
            im = im.convert("RGB")
        cut = remove(im, session=SESSION)                        # RGBA, background transparent
        t = to_tile(cut.convert("RGBA"), True)
        return t if t is not None else to_tile(im, False)        # fallback: the original picture on white
    except Exception:
        return None

def merge4(tiles):
    sheet = Image.new("RGB", (TILE * 2, TILE * 2), (255, 255, 255))
    for i, t in enumerate(tiles[:4]):
        sheet.paste(t, ((i % 2) * TILE, (i // 2) * TILE))
    buf = io.BytesIO(); sheet.save(buf, "WEBP", quality=QUALITY, method=6)
    return buf.getvalue()

def build_word(w):
    if not w.picked: return
    tiles = [t for t in (cutout(p) for p in w.picked) if t is not None]
    if not tiles: w.err = "background removal failed"; return
    name = re.sub(r'[\\/:*?"<>|]', "", "%s_%s_%s" % (w.en, w.od, w.hi)).strip()
    d = os.path.join(OUT, w.chapter); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name + ".webp"), "wb").write(merge4(tiles))

done = 0
with ThreadPoolExecutor(REMBG_WORKERS) as rp:
    futs = [rp.submit(build_word, w) for w in words]
    for f in as_completed(futs):
        try: f.result()
        except Exception as e: print("   error:", e)
        done += 1
        if done % 25 == 0 or done == len(words):
            print("   merged %d/%d words  [%.0f s total]" % (done, len(words), time.time() - t0))

# ---------------- report + zip ----------------
report = []
for w in words:
    status = "FAILED" if not w.picked else ("OK" if w.n_good >= 3 else ("CHECK" if w.n_good >= 1 else "LOW"))
    report.append([w.chapter, w.en, w.od, w.hi, status, w.n_good, round(w.conf, 3), w.rounds, w.err])
with open("verify_report.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([["chapter", "english", "odia", "hindi", "status", "good_pictures", "confidence", "rounds", "error"]] + report)
bad = [r for r in report if r[4] in ("LOW", "FAILED")]
chk = [r for r in report if r[4] == "CHECK"]
print("\nFinished in %.0f min: %d OK, %d CHECK, %d LOW/FAILED" % ((time.time() - t0) / 60, len(report) - len(bad) - len(chk), len(chk), len(bad)))
for r in bad: print("  LOW/FAILED:", r[0], r[1], r[4], r[8])

with zipfile.ZipFile("assets.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for root, ds, fs in os.walk(OUT):
        for fn in sorted(fs):
            p = os.path.join(root, fn); z.write(p, p.replace(os.sep, "/"))
    z.write("verify_report.csv")
print("assets.zip: %.1f MB" % (os.path.getsize("assets.zip") / 1048576))
shutil.rmtree(CACHE, ignore_errors=True)
try:
    from google.colab import files
    files.download("assets.zip")
except ImportError:
    print("Not in Colab: assets.zip is in the current folder")
