"""
Prompt bank for VoiceraCX speech data collection.
Each prompt is designed to elicit specific acoustic/linguistic patterns
relevant to the adapter training pipeline.

v2.0 — Expanded to ~100 prompts across 8 categories with improved
phonetic coverage for Indian English ASR training.
"""

PROMPTS = [
    # ── DOMAIN VOCABULARY ──────────────────────────────────────────────────────
    # Targets: OOV proper nouns, product names, jargon the model misrecognizes

    {"id": "dv_001", "category": "domain_vocabulary", "text": "I'd like to check my VoiceraCX account balance please."},
    {"id": "dv_002", "category": "domain_vocabulary", "text": "Can you connect me to the VoiceraCX support team?"},
    {"id": "dv_003", "category": "domain_vocabulary", "text": "I'm calling about my Pipecat integration issue."},
    {"id": "dv_004", "category": "domain_vocabulary", "text": "The LiveKit room is not connecting properly on my end."},
    {"id": "dv_005", "category": "domain_vocabulary", "text": "I need help setting up the Deepgram Nova transcription."},
    {"id": "dv_006", "category": "domain_vocabulary", "text": "My agent pipeline is throwing a CTC decoding error."},
    {"id": "dv_007", "category": "domain_vocabulary", "text": "Please reset my API key for the voice agent dashboard."},
    {"id": "dv_008", "category": "domain_vocabulary", "text": "I want to enable the WebSocket streaming endpoint."},
    {"id": "dv_009", "category": "domain_vocabulary", "text": "The KenLM language model is not loading correctly."},
    {"id": "dv_010", "category": "domain_vocabulary", "text": "I want to switch from Nova-2 to Nova-3 for better accuracy."},
    {"id": "dv_011", "category": "domain_vocabulary", "text": "Can you explain the Reciprocal Rank Fusion setup?"},
    {"id": "dv_012", "category": "domain_vocabulary", "text": "My Qdrant vector store is not syncing with the embeddings."},
    {"id": "dv_013", "category": "domain_vocabulary", "text": "The SpecAugment configuration needs to be updated."},
    {"id": "dv_014", "category": "domain_vocabulary", "text": "I need to retrain the adapter weights from last month's data."},
    {"id": "dv_015", "category": "domain_vocabulary", "text": "Our tenant on the VoiceraCX platform is reporting high latency."},

    # ── SIMULATED CUSTOMER QUERIES ─────────────────────────────────────────────
    # Targets: real call center speech patterns, spontaneous register

    {"id": "cq_001", "category": "customer_query", "text": "I want to cancel my subscription, can someone help me?"},
    {"id": "cq_002", "category": "customer_query", "text": "My payment was deducted but the service is still not activated."},
    {"id": "cq_003", "category": "customer_query", "text": "Can you tell me what plan I am currently on?"},
    {"id": "cq_004", "category": "customer_query", "text": "I need to update my billing address to a new location."},
    {"id": "cq_005", "category": "customer_query", "text": "The OTP I received is not working, please send a new one."},
    {"id": "cq_006", "category": "customer_query", "text": "I want to upgrade from the basic plan to the enterprise plan."},
    {"id": "cq_007", "category": "customer_query", "text": "How do I add a new user to my company account?"},
    {"id": "cq_008", "category": "customer_query", "text": "I have been waiting on hold for 20 minutes, this is unacceptable."},
    {"id": "cq_009", "category": "customer_query", "text": "My invoice shows extra charges that were not in my original quote."},
    {"id": "cq_010", "category": "customer_query", "text": "Can I speak to a senior support engineer please?"},
    {"id": "cq_011", "category": "customer_query", "text": "The voice bot is not understanding my accent properly."},
    {"id": "cq_012", "category": "customer_query", "text": "I would like a refund for last month's unused minutes."},
    {"id": "cq_013", "category": "customer_query", "text": "Please transfer my call to the technical team immediately."},
    {"id": "cq_014", "category": "customer_query", "text": "Is there any downtime scheduled for this weekend?"},
    {"id": "cq_015", "category": "customer_query", "text": "My account was suspended without any prior notification."},

    # ── HINGLISH / CODE-SWITCHED ───────────────────────────────────────────────
    # Targets: mid-sentence language switching, mixed register

    {"id": "hs_001", "category": "hinglish", "text": "Mujhe apna account check karna hai, please help me."},
    {"id": "hs_002", "category": "hinglish", "text": "Yeh OTP kab tak valid rahega, I need to know quickly."},
    {"id": "hs_003", "category": "hinglish", "text": "Please send me the invoice, mujhe abhi chahiye."},
    {"id": "hs_004", "category": "hinglish", "text": "Main bahut time se wait kar raha hoon, can you please check?"},
    {"id": "hs_005", "category": "hinglish", "text": "Mera subscription renew nahi hua, what should I do?"},
    {"id": "hs_006", "category": "hinglish", "text": "Yeh voice bot theek se kaam nahi kar raha, it keeps cutting off."},
    {"id": "hs_007", "category": "hinglish", "text": "Kya aap mujhe enterprise plan ke baare mein bata sakte hain?"},
    {"id": "hs_008", "category": "hinglish", "text": "Balance khatam ho gaya, please add more minutes to my account."},
    {"id": "hs_009", "category": "hinglish", "text": "Technical issue hai mujhe, the dashboard is showing an error."},
    {"id": "hs_010", "category": "hinglish", "text": "Call drop ho rahi hai again and again, please fix this."},
    {"id": "hs_011", "category": "hinglish", "text": "Mujhe ek refund chahiye, last month ka payment galat tha."},
    {"id": "hs_012", "category": "hinglish", "text": "Aap log har baar same answer dete ho, I need a proper solution."},

    # ── ALPHANUMERIC / CODES ───────────────────────────────────────────────────
    # Targets: confirmation codes, booking IDs, phone numbers — highest WER category

    {"id": "an_001", "category": "alphanumeric", "text": "My booking ID is B as in Bravo, 7, 4, 2, M as in Mike."},
    {"id": "an_002", "category": "alphanumeric", "text": "The confirmation code is A X 9 3 7 Z."},
    {"id": "an_003", "category": "alphanumeric", "text": "My phone number is 9 8 2 1 5 6 7 4 3 0."},
    {"id": "an_004", "category": "alphanumeric", "text": "The transaction reference is T R X dash 4 4 8 8 1 2."},
    {"id": "an_005", "category": "alphanumeric", "text": "My employee ID is E as in Echo, M 0 0 7 5."},
    {"id": "an_006", "category": "alphanumeric", "text": "The error code showing is 4 0 3 forbidden."},
    {"id": "an_007", "category": "alphanumeric", "text": "My API key starts with S K underscore live underscore X 9."},
    {"id": "an_008", "category": "alphanumeric", "text": "The invoice number is I N V dash 2 0 2 5 dash 0 0 1 4."},
    {"id": "an_009", "category": "alphanumeric", "text": "Please note the ticket number: T K T 8 8 3 2 7."},
    {"id": "an_010", "category": "alphanumeric", "text": "My GST number is 2 7 A A B C D 1 2 3 4 E 1 Z 5."},
    {"id": "an_011", "category": "alphanumeric", "text": "My Aadhaar number is 4 3 2 1 space 8 7 6 5 space 9 0 1 2."},
    {"id": "an_012", "category": "alphanumeric", "text": "My PAN card number is A B C P D 1 2 3 4 E."},

    # ── INDIAN ENGLISH PHONETIC ─────────────────────────────────────────────────
    # Targets: retroflex consonants, aspiration contrasts, word-final fricatives,
    #          vowel length, consonant clusters, connected speech patterns

    # Retroflex consonants in natural CX context
    {"id": "pi_001", "category": "phonetic_indian", "text": "The Hyderabad team will share the third quarter report by Thursday."},
    {"id": "pi_002", "category": "phonetic_indian", "text": "Please forward the data to our Dharavi distribution center today."},
    {"id": "pi_003", "category": "phonetic_indian", "text": "The total order was delivered to the Patna address without delay."},
    {"id": "pi_004", "category": "phonetic_indian", "text": "Our Ahmedabad partner returned the documents after the audit."},

    # Aspiration contrasts
    {"id": "pi_005", "category": "phonetic_indian", "text": "Please check the ticket from Chandigarh, the passenger changed the booking."},
    {"id": "pi_006", "category": "phonetic_indian", "text": "Take two tickets to the theatre and touch base with the team after."},
    {"id": "pi_007", "category": "phonetic_indian", "text": "Keep a copy of the package details before picking up the parcel."},

    # Word-final fricatives and affricates
    {"id": "pi_008", "category": "phonetic_indian", "text": "I wish to finish the refresh process without a crash."},
    {"id": "pi_009", "category": "phonetic_indian", "text": "The speech was rich, but which change would match our budget?"},
    {"id": "pi_010", "category": "phonetic_indian", "text": "The service charge applies to each of the five invoices."},
    {"id": "pi_011", "category": "phonetic_indian", "text": "Please watch the batch and catch any edge cases before the launch."},

    # Vowel length contrasts
    {"id": "pi_012", "category": "phonetic_indian", "text": "The team will leave the meeting early to reach the deal on time."},
    {"id": "pi_013", "category": "phonetic_indian", "text": "The ship will not fit in the sheep pen, and the bid beat the old offer."},
    {"id": "pi_014", "category": "phonetic_indian", "text": "Pull the full report and compare it to the pool of data we collected."},

    # Consonant clusters (initial and final)
    {"id": "pi_015", "category": "phonetic_indian", "text": "The strengths of this product include its smooth and structured design."},
    {"id": "pi_016", "category": "phonetic_indian", "text": "Please split the tasks and start the sprint before the next scheduled call."},
    {"id": "pi_017", "category": "phonetic_indian", "text": "The scripts and prompts were fixed in the twelfth build last month."},

    # Connected speech and coarticulation
    {"id": "pi_018", "category": "phonetic_indian", "text": "I want to know how you are going to manage this situation."},
    {"id": "pi_019", "category": "phonetic_indian", "text": "Could you tell me if the agent has already handled the complaint?"},
    {"id": "pi_020", "category": "phonetic_indian", "text": "He asked her to look into it and get back to him as soon as possible."},

    # ── NATURAL / DISFLUENT ─────────────────────────────────────────────────────
    # Targets: natural hesitations, self-corrections, real speech patterns

    {"id": "nf_001", "category": "disfluent", "text": "Um, I wanted to, uh, check on my account status, if that's okay."},
    {"id": "nf_002", "category": "disfluent", "text": "So basically, I have been charged twice, I mean, two times for the same thing."},
    {"id": "nf_003", "category": "disfluent", "text": "I called last week, or maybe it was the week before, and nobody got back to me."},
    {"id": "nf_004", "category": "disfluent", "text": "Can you, like, transfer me to someone who can actually help? No offense."},
    {"id": "nf_005", "category": "disfluent", "text": "The thing is, I don't know, I just want this resolved as soon as possible."},
    {"id": "nf_006", "category": "disfluent", "text": "Wait, wait, let me think, uh, so the issue started around, maybe Monday?"},
    {"id": "nf_007", "category": "disfluent", "text": "I tried to, you know, reset the password but then it, it just didn't work."},
    {"id": "nf_008", "category": "disfluent", "text": "Okay so basically what happened was, the payment went through but, uh, the confirmation never came."},

    # ── DATES & ADDRESSES (NEW) ─────────────────────────────────────────────────
    # Targets: Indian dates, addresses, PIN codes, city/state names

    {"id": "da_001", "category": "dates_addresses", "text": "My address is 42 M G Road, Bengaluru, Karnataka, PIN 560001."},
    {"id": "da_002", "category": "dates_addresses", "text": "The delivery date is 15th March 2025, please confirm."},
    {"id": "da_003", "category": "dates_addresses", "text": "I live at Flat 302, Sai Krupa Apartments, Banjara Hills, Hyderabad."},
    {"id": "da_004", "category": "dates_addresses", "text": "The appointment is on Tuesday, the 7th of January, at 10 30 AM."},
    {"id": "da_005", "category": "dates_addresses", "text": "Ship it to Plot 18, Sector 62, Noida, Uttar Pradesh, PIN 201309."},
    {"id": "da_006", "category": "dates_addresses", "text": "My date of birth is 23rd August 1990."},
    {"id": "da_007", "category": "dates_addresses", "text": "Send the parcel to 5th Cross, Jayanagar 4th Block, Bangalore."},
    {"id": "da_008", "category": "dates_addresses", "text": "The warranty expires on 31st December 2026, is that correct?"},
    {"id": "da_009", "category": "dates_addresses", "text": "I am calling from Andheri West, Mumbai, Maharashtra, PIN 400058."},
    {"id": "da_010", "category": "dates_addresses", "text": "Please schedule the visit for next Thursday between 2 PM and 4 PM."},

    # ── NUMBERS & CURRENCY (NEW) ────────────────────────────────────────────────
    # Targets: rupee amounts, percentages, measurements in natural speech

    {"id": "nc_001", "category": "numbers_currency", "text": "The total comes to rupees fourteen thousand nine hundred and fifty."},
    {"id": "nc_002", "category": "numbers_currency", "text": "I was charged three hundred and forty nine rupees extra this month."},
    {"id": "nc_003", "category": "numbers_currency", "text": "The interest rate is eight point seven five percent per annum."},
    {"id": "nc_004", "category": "numbers_currency", "text": "My EMI amount is twenty two thousand five hundred rupees per month."},
    {"id": "nc_005", "category": "numbers_currency", "text": "The package weighs two point five kilograms and costs sixty rupees per kilo."},
    {"id": "nc_006", "category": "numbers_currency", "text": "I need to transfer one lakh twenty five thousand rupees to this account."},
    {"id": "nc_007", "category": "numbers_currency", "text": "The discount is fifteen percent off the original price of four thousand."},
    {"id": "nc_008", "category": "numbers_currency", "text": "My account balance shows rupees seventy three thousand two hundred and eleven."},
]

CATEGORIES = {
    "domain_vocabulary": "Domain Vocabulary",
    "customer_query": "Customer Queries",
    "hinglish": "Hinglish / Code-switched",
    "alphanumeric": "Alphanumeric Codes",
    "phonetic_indian": "Indian English Phonetic",
    "disfluent": "Natural / Disfluent",
    "dates_addresses": "Dates & Addresses",
    "numbers_currency": "Numbers & Currency",
    # Legacy key for backward compatibility with existing recordings
    "phonetic": "Phonetic (legacy)",
}
