#!/usr/bin/env python3
"""
Voice Recording Studio for JARVIS Voice Cloning
=================================================
Interactive script that walks you through recording your voice for
StyleTTS2/Kokoro fine-tuning. Designed to be fun, not boring.

Records short clips (5-15 seconds each) across a variety of emotional
ranges, languages (English, Hindi, Hinglish), and speaking styles
(assistant responses, casual chat, storytelling, sarcasm, etc.).

Usage:
    python record_voice.py                   # Start fresh
    python record_voice.py --resume          # Continue from where you left off
    python record_voice.py --output-dir ./my_recordings
    python record_voice.py --list-prompts    # Preview all prompts without recording
    python record_voice.py --help

Requirements:
    pip install sounddevice soundfile numpy
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# Optional deps — graceful handling
try:
    import sounddevice as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False

try:
    import soundfile as sf
    HAS_SF = True
except ImportError:
    HAS_SF = False


# ═══════════════════════════════════════════════════════════════
# Recording prompts — 200+ covering all emotional/language ranges
# ═══════════════════════════════════════════════════════════════

PROMPTS = [
    # ── English: Assistant responses (neutral, warm) ──────────
    {"text": "Playing Sajni by Arijit Singh. Great choice, this one's beautiful.", "style": "assistant", "lang": "en"},
    {"text": "The weather today is twenty-eight degrees and sunny. Perfect day to go outside.", "style": "assistant", "lang": "en"},
    {"text": "Good morning! It's seven thirty. You have three meetings today.", "style": "assistant", "lang": "en"},
    {"text": "I've set the lights to warm orange at sixty percent brightness.", "style": "assistant", "lang": "en"},
    {"text": "Sure, playing your workout playlist. Let's get pumped!", "style": "assistant", "lang": "en"},
    {"text": "The time is currently four fifteen in the afternoon.", "style": "assistant", "lang": "en"},
    {"text": "I found three results for your question. The most relevant one says...", "style": "assistant", "lang": "en"},
    {"text": "Your alarm is set for six thirty tomorrow morning. Sleep well.", "style": "assistant", "lang": "en"},
    {"text": "Switching to movie mode. Lights dimming to ten percent.", "style": "assistant", "lang": "en"},
    {"text": "I've added milk, eggs, and bread to your shopping list.", "style": "assistant", "lang": "en"},
    {"text": "Playing Tum Hi Ho from Aashiqui Two. A classic.", "style": "assistant", "lang": "en"},
    {"text": "The cricket score is India two hundred and forty five for three wickets.", "style": "assistant", "lang": "en"},
    {"text": "Turning off all the lights. Goodnight!", "style": "assistant", "lang": "en"},
    {"text": "Here's what I found about the Jetson Orin Nano. It has eight gigabytes of shared memory.", "style": "assistant", "lang": "en"},
    {"text": "Volume set to forty percent. Let me know if you want it louder.", "style": "assistant", "lang": "en"},

    # ── English: Conversational / casual ──────────────────────
    {"text": "Yeah, I think that's a pretty good idea actually.", "style": "casual", "lang": "en"},
    {"text": "Oh come on, that movie was terrible and you know it!", "style": "casual", "lang": "en"},
    {"text": "I mean, it's not the worst thing in the world, but still.", "style": "casual", "lang": "en"},
    {"text": "So basically what happened was, the whole thing just crashed.", "style": "casual", "lang": "en"},
    {"text": "Honestly, I have no idea how that even works.", "style": "casual", "lang": "en"},
    {"text": "That's actually really cool. I didn't know that.", "style": "casual", "lang": "en"},
    {"text": "Wait wait wait, are you serious right now?", "style": "casual", "lang": "en"},
    {"text": "Okay fine, you win. I'll admit it, you were right.", "style": "casual", "lang": "en"},
    {"text": "Dude, you have to try this biryani. It's incredible.", "style": "casual", "lang": "en"},
    {"text": "I've been coding for like twelve hours straight. My brain is fried.", "style": "casual", "lang": "en"},
    {"text": "The thing about machine learning is, it's not actually that complicated once you get it.", "style": "casual", "lang": "en"},
    {"text": "Let me think about this for a second. Yeah, I think we should go with option two.", "style": "casual", "lang": "en"},
    {"text": "No way! That's the same restaurant we went to last time!", "style": "casual", "lang": "en"},
    {"text": "I'm telling you, this is going to be amazing. Just trust me on this.", "style": "casual", "lang": "en"},
    {"text": "So the thing is, you need to understand the context first before jumping to conclusions.", "style": "casual", "lang": "en"},

    # ── English: Questions ────────────────────────────────────
    {"text": "What would you like to listen to tonight?", "style": "question", "lang": "en"},
    {"text": "Should I turn the lights off or dim them?", "style": "question", "lang": "en"},
    {"text": "Do you want me to play something relaxing?", "style": "question", "lang": "en"},
    {"text": "Are you sure you want to skip this song?", "style": "question", "lang": "en"},
    {"text": "Would you prefer the romantic playlist or the chill one?", "style": "question", "lang": "en"},
    {"text": "Did you mean Sajni by Arijit Singh or Sajni by Jal?", "style": "question", "lang": "en"},
    {"text": "How about we try something different tonight?", "style": "question", "lang": "en"},
    {"text": "Want me to set a reminder for that?", "style": "question", "lang": "en"},
    {"text": "What color should I set the lights to?", "style": "question", "lang": "en"},
    {"text": "Shall I continue with the story or would you like to sleep now?", "style": "question", "lang": "en"},

    # ── English: Excited / enthusiastic ───────────────────────
    {"text": "Oh this is a great song! Arijit Singh never disappoints.", "style": "excited", "lang": "en"},
    {"text": "Yes! You got the answer right! That's five in a row!", "style": "excited", "lang": "en"},
    {"text": "Happy birthday! I hope you have the most amazing day!", "style": "excited", "lang": "en"},
    {"text": "India won the match! What a comeback that was!", "style": "excited", "lang": "en"},
    {"text": "Guess what? Your favorite artist just released a new album!", "style": "excited", "lang": "en"},
    {"text": "That's amazing news! I'm so happy for you!", "style": "excited", "lang": "en"},
    {"text": "Wow, you finished the whole playlist? Impressive!", "style": "excited", "lang": "en"},
    {"text": "Party mode activated! Let's go!", "style": "excited", "lang": "en"},
    {"text": "Coldplay is coming to India! Want me to check ticket prices?", "style": "excited", "lang": "en"},
    {"text": "That was the perfect answer! You're a genius!", "style": "excited", "lang": "en"},

    # ── English: Calm / soothing ──────────────────────────────
    {"text": "It's been a long day. How about some relaxing music?", "style": "calm", "lang": "en"},
    {"text": "Good night. Sweet dreams. I'll be here when you wake up.", "style": "calm", "lang": "en"},
    {"text": "Take a deep breath. Everything is going to be fine.", "style": "calm", "lang": "en"},
    {"text": "The rain sounds are playing softly. Just close your eyes and relax.", "style": "calm", "lang": "en"},
    {"text": "Once upon a time, in a quiet little village near the mountains...", "style": "calm", "lang": "en"},
    {"text": "The moonlight was streaming through the window, casting silver shadows on the floor.", "style": "calm", "lang": "en"},
    {"text": "I've dimmed the lights to five percent. Sleep mode is on.", "style": "calm", "lang": "en"},
    {"text": "Just relax. I'm playing some soft instrumental music for you.", "style": "calm", "lang": "en"},
    {"text": "The stars are out tonight. It's a beautiful, quiet evening.", "style": "calm", "lang": "en"},
    {"text": "Let the music wash over you. There's nowhere you need to be right now.", "style": "calm", "lang": "en"},

    # ── English: Sarcastic / funny ────────────────────────────
    {"text": "Oh sure, let me just Google that for you. Oh wait, I already did.", "style": "sarcastic", "lang": "en"},
    {"text": "You want me to play Baby Shark? Really? I expected better from you.", "style": "sarcastic", "lang": "en"},
    {"text": "Congratulations, you've asked me the time for the fourteenth time today.", "style": "sarcastic", "lang": "en"},
    {"text": "Could this BE any more of a Chandler Bing moment?", "style": "sarcastic", "lang": "en"},
    {"text": "Oh wow, another Monday. How exciting. I can barely contain myself.", "style": "sarcastic", "lang": "en"},
    {"text": "Sure, I'll set the alarm for five AM. Your funeral.", "style": "sarcastic", "lang": "en"},
    {"text": "Bold choice playing sad songs at a party. Very on brand.", "style": "sarcastic", "lang": "en"},
    {"text": "I would judge your music taste, but I'm a computer, so I'll just silently judge.", "style": "sarcastic", "lang": "en"},
    {"text": "Oh, you want to hear that song again? The one you've played twenty-seven times today?", "style": "sarcastic", "lang": "en"},
    {"text": "Breaking news: water is wet. Anything else you'd like me to confirm?", "style": "sarcastic", "lang": "en"},

    # ── English: Technical explanations ───────────────────────
    {"text": "Quantization reduces model weights from thirty-two bit floats to eight bit integers, cutting memory by four X.", "style": "technical", "lang": "en"},
    {"text": "The transformer architecture uses self-attention to weigh the importance of different input tokens.", "style": "technical", "lang": "en"},
    {"text": "ONNX Runtime is a cross-platform inference engine that supports CUDA, CoreML, and CPU execution providers.", "style": "technical", "lang": "en"},
    {"text": "The Jetson Orin Nano has a six-core ARM CPU and a thousand twenty four CUDA cores with eight gigs of unified memory.", "style": "technical", "lang": "en"},
    {"text": "Faster Whisper uses CTranslate two, which is a C plus plus inference engine optimized for transformer models.", "style": "technical", "lang": "en"},
    {"text": "A style vector captures the prosody, timbre, and speaking rate of a voice in a fixed dimensional embedding.", "style": "technical", "lang": "en"},
    {"text": "The mel spectrogram converts raw audio into a time-frequency representation that neural networks can process.", "style": "technical", "lang": "en"},
    {"text": "Flow matching is like diffusion but more efficient. It learns a direct path from noise to data.", "style": "technical", "lang": "en"},
    {"text": "HiFi GAN is a vocoder that converts mel spectrograms back into audible waveforms at high quality.", "style": "technical", "lang": "en"},
    {"text": "Provider pattern means every component is swappable. Change one line in config, no code changes needed.", "style": "technical", "lang": "en"},

    # ── English: Storytelling / bedtime ───────────────────────
    {"text": "A long time ago, there lived a wise old owl in the deepest part of an enchanted forest.", "style": "story", "lang": "en"},
    {"text": "The little robot blinked its lights and said, I think I'm alive. And the scientist smiled.", "style": "story", "lang": "en"},
    {"text": "Every night, the stars would whisper secrets to the moon, and the moon would tell them to the sea.", "style": "story", "lang": "en"},
    {"text": "And so the brave little ship sailed on, past the storm, past the darkness, into the golden sunrise.", "style": "story", "lang": "en"},
    {"text": "The dragon wasn't scary at all. In fact, he was quite shy and loved to read books.", "style": "story", "lang": "en"},
    {"text": "She opened the old wooden door and found a garden filled with flowers that glowed in the moonlight.", "style": "story", "lang": "en"},
    {"text": "And they lived happily ever after. The end. Now close your eyes and dream of adventures.", "style": "story", "lang": "en"},
    {"text": "In a city made entirely of glass, there was one building that was made of wood. And that's where our story begins.", "style": "story", "lang": "en"},
    {"text": "The wizard looked at his broken wand and laughed. Magic, he said, was never in the wand.", "style": "story", "lang": "en"},
    {"text": "Far away, beyond the seven mountains, there was a land where music could make flowers bloom.", "style": "story", "lang": "en"},

    # ── Hindi sentences ───────────────────────────────────────
    {"text": "Arijit Singh ka naya gaana play kar raha hoon. Bahut achha gaana hai.", "style": "assistant", "lang": "hi"},
    {"text": "Aaj ka mausam bahut achha hai. Bahar dhoop nikli hai.", "style": "assistant", "lang": "hi"},
    {"text": "Lights ko laal rang mein set kar diya hai.", "style": "assistant", "lang": "hi"},
    {"text": "Shubh raatri! Achhe sapne dekhna. Kal subah milte hain.", "style": "calm", "lang": "hi"},
    {"text": "Bahut bahut badhaai ho! Yeh toh kamaal ki khabar hai!", "style": "excited", "lang": "hi"},
    {"text": "Ek baar ki baat hai, ek chhote se gaanv mein ek buddhaa pedh thaa.", "style": "story", "lang": "hi"},
    {"text": "Kya aapko koi aur gaana sunna hai?", "style": "question", "lang": "hi"},
    {"text": "Main aapke liye kuch dhundhta hoon. Ek second ruko.", "style": "assistant", "lang": "hi"},
    {"text": "Aaj Sunday hai. Aaram karo, koi jaldi nahi hai.", "style": "calm", "lang": "hi"},
    {"text": "Kya baat kar rahe ho! Yeh toh bahut funny hai!", "style": "excited", "lang": "hi"},
    {"text": "Sochne do ek second. Haan, main samajh gaya.", "style": "casual", "lang": "hi"},
    {"text": "Mujhe lagta hai aaj barish hone wali hai. Chhatri le jaana.", "style": "assistant", "lang": "hi"},
    {"text": "Neend aa rahi hai? Chalo koi achhi si kahani sunata hoon.", "style": "calm", "lang": "hi"},
    {"text": "Volume thoda aur badhaa deta hoon. Ab theek hai?", "style": "assistant", "lang": "hi"},
    {"text": "Kya aap sure hain? Ek baar aur soch lo.", "style": "question", "lang": "hi"},
    {"text": "Bahut der ho gayi hai. Aapko so jaana chahiye.", "style": "calm", "lang": "hi"},
    {"text": "Arre waah! Kya shot maara hai! India jeet raha hai!", "style": "excited", "lang": "hi"},
    {"text": "Chalo quiz khelte hain. Pehla sawaal tayyar ho?", "style": "excited", "lang": "hi"},
    {"text": "Sahi jawaab! Aap toh genius ho!", "style": "excited", "lang": "hi"},
    {"text": "Galat jawaab. Koi baat nahi, agli baar sahi karoge.", "style": "calm", "lang": "hi"},

    # ── Hinglish: Mixed Hindi-English (Devesh's natural style) ─
    {"text": "Bro, this song is fire yaar. Arijit Singh ne kamaal kar diya.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Yaar main bahut tired hoon. Twelve hours se code kar raha hoon.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Okay so basically, kya hua ki server crash ho gaya. Phir restart kiya.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Let me check karta hoon. Haan, aaj ka weather bahut achha hai.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Biryani khaaoge? Main order kar deta hoon Swiggy se.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Machine learning actually itna difficult nahi hai. Bas patience chahiye.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Arre no way yaar! Same pinch! Main bhi yehi soch raha tha!", "style": "hinglish", "lang": "hi-en"},
    {"text": "So the plan is ki hum pehle code likhenge, phir test karenge, phir deploy.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Coldplay ka concert attend karna hai yaar. Tickets mil jaayein bas.", "style": "hinglish", "lang": "hi-en"},
    {"text": "This momos wala near office makes the best momos ever. Seriously try karo.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Aaj mood nahi hai kuch karne ka. Netflix pe kuch dekhte hain.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Bhai mujhe lagta hai yeh approach better hai. Let me explain why.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Ek second ruk. Main Google karta hoon. Haan, yeh correct hai.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Tum sahi keh rahe ho actually. My bad, main galat tha.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Party tonight! Everyone's coming. It's gonna be epic yaar!", "style": "hinglish", "lang": "hi-en"},
    {"text": "Main kehta hoon na, patience rakho. Sab ho jaayega.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Docker container phir se crash ho gaya. Kya life hai yaar.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Chai pi lo pehle. Phir baat karte hain calmly.", "style": "hinglish", "lang": "hi-en"},
    {"text": "GPU utilization hundred percent hai. Model train ho raha hai full speed pe.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Weekend pe kya plan hai? Let's do something fun for a change.", "style": "hinglish", "lang": "hi-en"},

    # ── English: Emotional range — gentle sadness ─────────────
    {"text": "I know today was tough. But tomorrow is a new day, and I'll be right here.", "style": "gentle", "lang": "en"},
    {"text": "Sometimes things don't go the way we planned. And that's okay.", "style": "gentle", "lang": "en"},
    {"text": "Hey, it's alright to feel that way. Everyone has days like this.", "style": "gentle", "lang": "en"},
    {"text": "I'm here if you want to talk. Or I can just play some quiet music.", "style": "gentle", "lang": "en"},
    {"text": "You've done so much already. Give yourself some credit.", "style": "gentle", "lang": "en"},

    # ── English: Confident / assertive ────────────────────────
    {"text": "Done. The lights are set, the music is playing, and everything is under control.", "style": "confident", "lang": "en"},
    {"text": "I've got this. Just sit back and relax.", "style": "confident", "lang": "en"},
    {"text": "No problem at all. Consider it done.", "style": "confident", "lang": "en"},
    {"text": "Trust me on this one. I know exactly what song you're thinking of.", "style": "confident", "lang": "en"},
    {"text": "Already handled. Your alarm is set and lights will turn on automatically at seven.", "style": "confident", "lang": "en"},

    # ── English: Apologetic / uncertain ───────────────────────
    {"text": "I'm sorry, I didn't quite catch that. Could you say it again?", "style": "apologetic", "lang": "en"},
    {"text": "Hmm, I'm not sure about that one. Let me look it up.", "style": "apologetic", "lang": "en"},
    {"text": "I couldn't find that song. Could you give me more details?", "style": "apologetic", "lang": "en"},
    {"text": "Sorry about that. The music player seems to be having issues.", "style": "apologetic", "lang": "en"},
    {"text": "I might be wrong about this, but I think the answer is forty-two.", "style": "apologetic", "lang": "en"},

    # ── Numbers, dates, and edge cases for TTS ────────────────
    {"text": "The temperature is thirty-two point five degrees Celsius.", "style": "assistant", "lang": "en"},
    {"text": "Your meeting is at two thirty PM on Wednesday, April twenty-first.", "style": "assistant", "lang": "en"},
    {"text": "The song has been played one thousand four hundred and twenty times.", "style": "assistant", "lang": "en"},
    {"text": "Wi-Fi signal strength is at eighty-seven percent. Connection is stable.", "style": "assistant", "lang": "en"},
    {"text": "Battery is at fifteen percent. You might want to plug in soon.", "style": "assistant", "lang": "en"},

    # ── English: Longer, more complex sentences ───────────────
    {"text": "Alright, so I've turned on the party lights with purple and blue, set the volume to seventy, and queued up your Bollywood dance playlist. Let's get this started!", "style": "assistant", "lang": "en"},
    {"text": "Based on what I found, the restaurant has four point three stars, is about a fifteen minute drive, and they have great reviews for their butter chicken.", "style": "assistant", "lang": "en"},
    {"text": "I notice you've been listening to a lot of Arijit Singh lately. Would you like me to create a playlist with similar artists like Atif Aslam and Jubin Nautiyal?", "style": "assistant", "lang": "en"},
    {"text": "The story so far: a young programmer built a voice assistant for his girlfriend's birthday, and it turned out to be the most thoughtful gift she'd ever received.", "style": "story", "lang": "en"},
    {"text": "Let me break it down for you. First, the audio goes through a mel spectrogram transform. Then the style encoder extracts your voice characteristics. Finally, the decoder generates speech that sounds like you.", "style": "technical", "lang": "en"},

    # ── Hinglish: Longer sentences ────────────────────────────
    {"text": "Yaar sun, mujhe lagta hai ki hum iss weekend Goa chal sakte hain. Weather bhi achha hai aur flights bhi cheap mil jaayengi.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Toh basically kya hua ki main ne transformer architecture samajh liya, and now attention mechanism makes so much more sense.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Aaj dinner mein pizza mangwate hain ya phir biryani? Actually dono mangwa lete hain, why not.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Main bol raha hoon na, yeh project bahut amazing hoga. Just give it some time aur dekhna magic hoga.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Code review mein bahut saare comments aaye hain. But honestly, most of them are valid points yaar.", "style": "hinglish", "lang": "hi-en"},

    # ── Hindi: Longer sentences ───────────────────────────────
    {"text": "Aaj ka din bahut achha raha. Subah se sab kuch smooth chal raha hai aur mood bhi bahut achha hai.", "style": "casual", "lang": "hi"},
    {"text": "Ek kahaani sunao? Theek hai. Bahut puraani baat hai, jab duniya mein jaadu hua karta tha.", "style": "story", "lang": "hi"},
    {"text": "Mausam bahut pyaara hai aaj. Thandi hawa chal rahi hai aur aasmaan mein taare chamak rahe hain.", "style": "calm", "lang": "hi"},
    {"text": "Khana bana lo, chai pi lo, aur phir aaram se ek achhi movie dekho. Yehi toh life hai.", "style": "calm", "lang": "hi"},
    {"text": "Cricket mein aaj India ne kamaal ka match khela. Virat ne century maari aur sab pagal ho gaye.", "style": "excited", "lang": "hi"},

    # ── English: Whispered / soft ─────────────────────────────
    {"text": "Shh, the baby is sleeping. Let me play some very soft music.", "style": "whisper", "lang": "en"},
    {"text": "It's very late. Everyone's asleep. I'll keep my voice down.", "style": "whisper", "lang": "en"},
    {"text": "Just between us, I think you made the right choice.", "style": "whisper", "lang": "en"},

    # ── English: Counting / lists ─────────────────────────────
    {"text": "One, two, three, four, five. Testing, testing. Can you hear me clearly?", "style": "neutral", "lang": "en"},
    {"text": "First item: groceries. Second: pick up laundry. Third: call mom. Got it.", "style": "neutral", "lang": "en"},
    {"text": "A, B, C, D, E, F, G. The alphabet song but without the melody.", "style": "neutral", "lang": "en"},

    # ── English: Short, punchy ────────────────────────────────
    {"text": "Done.", "style": "short", "lang": "en"},
    {"text": "Got it. Playing now.", "style": "short", "lang": "en"},
    {"text": "Sure thing.", "style": "short", "lang": "en"},
    {"text": "On it.", "style": "short", "lang": "en"},
    {"text": "Absolutely!", "style": "short", "lang": "en"},
    {"text": "Not a chance.", "style": "short", "lang": "en"},
    {"text": "Of course.", "style": "short", "lang": "en"},
    {"text": "Right away.", "style": "short", "lang": "en"},
    {"text": "Hmm, interesting.", "style": "short", "lang": "en"},
    {"text": "Wait, what?", "style": "short", "lang": "en"},

    # ── Phonetically challenging (good for training) ──────────
    {"text": "Peter Piper picked a peck of pickled peppers. A peck of pickled peppers Peter Piper picked.", "style": "neutral", "lang": "en"},
    {"text": "She sells seashells by the seashore. The shells she sells are seashells I'm sure.", "style": "neutral", "lang": "en"},
    {"text": "The sixth sick sheik's sixth sheep's sick. Try saying that five times fast.", "style": "neutral", "lang": "en"},
    {"text": "How much wood would a woodchuck chuck if a woodchuck could chuck wood?", "style": "neutral", "lang": "en"},
    {"text": "Red lorry, yellow lorry. Red lorry, yellow lorry. Okay that one's hard.", "style": "neutral", "lang": "en"},

    # ── Hindi: Phonetically rich ──────────────────────────────
    {"text": "Kaccha papad, pakka papad. Kaccha papad, pakka papad.", "style": "neutral", "lang": "hi"},
    {"text": "Chandu ke chacha ne chandu ki chachi ko chandni chowk mein chaandi ki chamach se chatni chataayi.", "style": "neutral", "lang": "hi"},
    {"text": "Samajh samajh ke samajh ko samjho, samajh samajhna bhi ek samajh hai.", "style": "neutral", "lang": "hi"},

    # ── English: Emotional monologues (3-4 sentences) ─────────
    {"text": "You know what I love about music? It doesn't judge you. It doesn't ask questions. It just holds you and says, I understand.", "style": "gentle", "lang": "en"},
    {"text": "I think the best gifts are the ones that say, I thought about you. Not the expensive ones. The thoughtful ones.", "style": "gentle", "lang": "en"},
    {"text": "There's something magical about three AM. The world is quiet, the code flows better, and it feels like time stands still.", "style": "calm", "lang": "en"},
    {"text": "Every line of code is a tiny decision. And a thousand tiny decisions, made with care, become something beautiful.", "style": "calm", "lang": "en"},
    {"text": "The thing nobody tells you about building something from scratch is how many times you'll want to give up. But you don't. And that's the whole story.", "style": "gentle", "lang": "en"},

    # ── Filler / additional variety to reach 200+ ─────────────
    {"text": "Alright, let's see what we've got here.", "style": "casual", "lang": "en"},
    {"text": "Playing lo-fi hip hop beats to study and relax to.", "style": "assistant", "lang": "en"},
    {"text": "Setting the scene: romantic lighting, soft jazz, volume at thirty.", "style": "assistant", "lang": "en"},
    {"text": "That reminds me of a joke. Actually, never mind, it's terrible.", "style": "sarcastic", "lang": "en"},
    {"text": "I've been thinking, and I think you should take a break.", "style": "gentle", "lang": "en"},
    {"text": "Okay Google. Just kidding, it's me, Jarvis.", "style": "sarcastic", "lang": "en"},
    {"text": "Fun fact: did you know that honey never spoils? Archaeologists found three thousand year old honey and it was still good.", "style": "casual", "lang": "en"},
    {"text": "Switching to Devesh mode. Hey, kya haal hai yaar?", "style": "hinglish", "lang": "hi-en"},
    {"text": "Abhi toh party shuru hui hai. Night is still young, let's keep the music going.", "style": "hinglish", "lang": "hi-en"},
    {"text": "Main soch raha tha, agar hum AI se baat kar sakte hain, toh AI bhi humse baat kyon nahi kar sakta?", "style": "hinglish", "lang": "hi-en"},
    {"text": "Timer set for twenty-five minutes. Pomodoro technique, nice choice.", "style": "assistant", "lang": "en"},
    {"text": "Quick update: it's raining outside. You might want to take an umbrella.", "style": "assistant", "lang": "en"},
    {"text": "Shuffling your liked songs. Over three hundred songs to choose from.", "style": "assistant", "lang": "en"},
    {"text": "Focus mode activated. Notifications silenced. It's you and the code now.", "style": "confident", "lang": "en"},
    {"text": "I checked and the pizza place closes at eleven. Better order soon!", "style": "casual", "lang": "en"},
    {"text": "New message from Mom: Don't forget to eat properly. Classic.", "style": "sarcastic", "lang": "en"},
    {"text": "Aaj bahut garmi hai. AC chala de? Temperature twenty-four pe set kar deta hoon.", "style": "hinglish", "lang": "hi-en"},
    {"text": "You've been sitting for two hours straight. Maybe stand up and stretch?", "style": "gentle", "lang": "en"},
    {"text": "Next up: Channa Mereya by Arijit Singh. Tissues ready?", "style": "sarcastic", "lang": "en"},
    {"text": "I love this part of the day. When everything's quiet and the world slows down.", "style": "calm", "lang": "en"},
]

# Style display info for visual feedback
STYLE_COLORS = {
    "assistant": "\033[94m",     # blue
    "casual": "\033[92m",        # green
    "question": "\033[96m",      # cyan
    "excited": "\033[93m",       # yellow
    "calm": "\033[95m",          # magenta
    "sarcastic": "\033[91m",     # red
    "technical": "\033[37m",     # gray
    "story": "\033[35m",         # purple
    "hinglish": "\033[33m",      # dark yellow
    "gentle": "\033[95m",        # magenta
    "confident": "\033[94m",     # blue
    "apologetic": "\033[37m",    # gray
    "whisper": "\033[90m",       # dark gray
    "neutral": "\033[0m",        # default
    "short": "\033[92m",         # green
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


# ═══════════════════════════════════════════════════════════════
# Audio helpers
# ═══════════════════════════════════════════════════════════════

SAMPLE_RATE = 24000  # Kokoro/StyleTTS2 native rate
CHANNELS = 1


def detect_silence_threshold(duration: float = 1.0) -> float:
    """
    Record a short sample of background noise and compute a silence threshold.
    Returns an RMS value slightly above the ambient noise floor.
    """
    print(f"{DIM}  Calibrating microphone... (stay quiet for 1 second){RESET}")
    noise = sd.rec(int(SAMPLE_RATE * duration), samplerate=SAMPLE_RATE,
                   channels=CHANNELS, dtype="float32")
    sd.wait()
    rms = np.sqrt(np.mean(noise ** 2))
    threshold = rms * 3.0  # 3x ambient noise floor
    return max(threshold, 0.005)  # floor at 0.005 to avoid zero-threshold


def trim_silence(audio: np.ndarray, threshold: float, margin: int = 2400) -> np.ndarray:
    """
    Trim leading and trailing silence from an audio clip.
    margin: samples to keep as padding (100ms at 24kHz = 2400 samples).
    """
    if audio.ndim > 1:
        audio_mono = audio[:, 0]
    else:
        audio_mono = audio

    # Compute RMS in windows
    window_size = 1200  # 50ms windows
    n_windows = len(audio_mono) // window_size
    if n_windows == 0:
        return audio

    rms_values = np.array([
        np.sqrt(np.mean(audio_mono[i * window_size:(i + 1) * window_size] ** 2))
        for i in range(n_windows)
    ])

    # Find first and last non-silent window
    voiced = np.where(rms_values > threshold)[0]
    if len(voiced) == 0:
        return audio  # all silence — return as-is

    start_sample = max(0, voiced[0] * window_size - margin)
    end_sample = min(len(audio), (voiced[-1] + 1) * window_size + margin)

    return audio[start_sample:end_sample]


def record_clip(max_seconds: float = 20.0, silence_threshold: float = 0.01,
                silence_duration: float = 1.5) -> np.ndarray:
    """
    Record audio until silence is detected or max_seconds is reached.

    Uses a streaming approach: records in chunks, detects trailing silence,
    auto-stops when the user finishes speaking.

    Returns float32 numpy array at SAMPLE_RATE.
    """
    chunk_duration = 0.1  # 100ms chunks
    chunk_samples = int(SAMPLE_RATE * chunk_duration)
    max_chunks = int(max_seconds / chunk_duration)
    silence_chunks_needed = int(silence_duration / chunk_duration)

    chunks = []
    silent_count = 0
    has_speech = False

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype="float32", blocksize=chunk_samples)
    stream.start()

    try:
        for i in range(max_chunks):
            data, overflowed = stream.read(chunk_samples)
            chunks.append(data.copy())

            rms = np.sqrt(np.mean(data ** 2))

            if rms > silence_threshold:
                has_speech = True
                silent_count = 0
            else:
                silent_count += 1

            # Auto-stop: detected speech followed by silence
            if has_speech and silent_count >= silence_chunks_needed:
                break

            # Visual feedback: simple level meter
            level = min(int(rms * 500), 30)
            bar = "|" * level + " " * (30 - level)
            elapsed = (i + 1) * chunk_duration
            sys.stdout.write(f"\r  Recording [{bar}] {elapsed:.1f}s ")
            sys.stdout.flush()

    finally:
        stream.stop()
        stream.close()

    sys.stdout.write("\r" + " " * 60 + "\r")  # clear the recording line
    sys.stdout.flush()

    if not chunks:
        return np.array([], dtype="float32")

    audio = np.concatenate(chunks, axis=0)
    return audio


def play_audio(audio: np.ndarray):
    """Play back a recorded clip for review."""
    sd.play(audio, samplerate=SAMPLE_RATE)
    sd.wait()


def save_wav(audio: np.ndarray, filepath: Path):
    """Save audio as 24kHz mono WAV."""
    # Ensure mono
    if audio.ndim > 1:
        audio = audio[:, 0]
    sf.write(str(filepath), audio, SAMPLE_RATE, subtype="PCM_16")


# ═══════════════════════════════════════════════════════════════
# Progress tracking
# ═══════════════════════════════════════════════════════════════

def load_progress(progress_file: Path) -> dict:
    """Load recording progress from JSON file."""
    if progress_file.exists():
        with open(progress_file) as f:
            return json.load(f)
    return {"completed": [], "total_duration_seconds": 0.0}


def save_progress(progress_file: Path, progress: dict):
    """Save recording progress to JSON file."""
    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)


def format_duration(seconds: float) -> str:
    """Format seconds as 'Xm Ys'."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# ═══════════════════════════════════════════════════════════════
# Encouragement messages (randomized)
# ═══════════════════════════════════════════════════════════════

ENCOURAGEMENTS = [
    "Nailed it!",
    "Perfect. Moving on.",
    "That sounded great!",
    "Excellent. Your voice model is gonna love this.",
    "Solid. Keep going!",
    "Beautiful delivery.",
    "Nice one!",
    "Saved. You're doing great.",
    "Another one in the bag!",
    "Smooth. Next!",
    "Your AI clone is getting smarter.",
    "That was clean. Love it.",
    "Bang on. Let's keep the momentum.",
    "Locked in. Next prompt!",
    "Chef's kiss. Perfect take.",
    "Good energy on that one!",
    "Recorded and saved. You're a natural.",
    "That's the one. Moving on.",
    "Brilliant. Keep that energy!",
    "The voice model is going to be fire with this data.",
]


# ═══════════════════════════════════════════════════════════════
# Main recording loop
# ═══════════════════════════════════════════════════════════════

def print_header():
    """Print the welcome banner."""
    print(f"""
{BOLD}{'=' * 60}
   JARVIS Voice Recording Studio
   Record your voice for StyleTTS2 / Kokoro fine-tuning
{'=' * 60}{RESET}

  Controls:
    {BOLD}Enter{RESET}     = Start recording (auto-stops on silence)
    {BOLD}s{RESET}         = Skip this prompt
    {BOLD}r{RESET}         = Re-record the last clip
    {BOLD}p{RESET}         = Play back the last recording
    {BOLD}q{RESET}         = Quit (progress is saved)

  Tips:
    - Speak naturally, like you're talking to a friend
    - Match the style hint (excited, calm, sarcastic, etc.)
    - Don't worry about mistakes — you can re-record
    - Aim for 5-15 seconds per clip
    - The mic auto-stops when you finish speaking
""")


def show_progress_bar(completed: int, total: int, duration_sec: float):
    """Show a visual progress bar."""
    pct = completed / total if total > 0 else 0
    filled = int(40 * pct)
    bar = "#" * filled + "-" * (40 - filled)
    print(f"\n  [{bar}] {completed}/{total} ({pct:.0%}) | {format_duration(duration_sec)} recorded\n")


def main():
    parser = argparse.ArgumentParser(
        description="Voice Recording Studio for JARVIS voice cloning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python record_voice.py                    # Start fresh
  python record_voice.py --resume           # Continue from last session
  python record_voice.py --list-prompts     # Preview all prompts
  python record_voice.py --output-dir ~/my_recordings
        """
    )
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to save recordings (default: ./recordings)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from where you left off")
    parser.add_argument("--list-prompts", action="store_true",
                        help="List all prompts without recording")
    parser.add_argument("--start-from", type=int, default=0,
                        help="Start from prompt number N (0-indexed)")
    args = parser.parse_args()

    # List prompts mode
    if args.list_prompts:
        print(f"\n{BOLD}All {len(PROMPTS)} recording prompts:{RESET}\n")
        for i, p in enumerate(PROMPTS):
            color = STYLE_COLORS.get(p["style"], "")
            print(f"  {i:3d}. [{p['style']:12s}] [{p['lang']:5s}] {color}{p['text']}{RESET}")
        print(f"\n  Styles: {', '.join(sorted(set(p['style'] for p in PROMPTS)))}")
        print(f"  Languages: {', '.join(sorted(set(p['lang'] for p in PROMPTS)))}")
        return

    # Check dependencies
    if not HAS_SD:
        print("ERROR: sounddevice not installed. Run: pip install sounddevice")
        sys.exit(1)
    if not HAS_SF:
        print("ERROR: soundfile not installed. Run: pip install soundfile")
        sys.exit(1)

    # Setup directories
    base_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent / "recordings"
    base_dir.mkdir(parents=True, exist_ok=True)
    progress_file = base_dir / "progress.json"

    # Load progress
    progress = load_progress(progress_file)
    if args.resume:
        completed_set = set(progress.get("completed", []))
    else:
        completed_set = set()
        if args.start_from == 0:
            progress = {"completed": [], "total_duration_seconds": 0.0}

    total_duration = progress.get("total_duration_seconds", 0.0)

    print_header()

    # Calibrate mic
    try:
        silence_threshold = detect_silence_threshold()
        print(f"  Silence threshold: {silence_threshold:.4f} RMS")
    except Exception as e:
        print(f"  Warning: Could not calibrate mic ({e}). Using default threshold.")
        silence_threshold = 0.01

    print(f"  Output directory: {base_dir}")
    print(f"  Total prompts: {len(PROMPTS)}")
    show_progress_bar(len(completed_set), len(PROMPTS), total_duration)

    import random
    enc_idx = 0

    last_audio = None
    last_filepath = None

    # Determine starting point
    start_idx = args.start_from
    if args.resume and completed_set:
        # Find the first uncompleted prompt
        for i in range(len(PROMPTS)):
            if i not in completed_set:
                start_idx = i
                break

    for idx in range(start_idx, len(PROMPTS)):
        if idx in completed_set:
            continue

        prompt = PROMPTS[idx]
        style = prompt["style"]
        lang = prompt["lang"]
        text = prompt["text"]
        color = STYLE_COLORS.get(style, "")

        remaining = len(PROMPTS) - len(completed_set)

        # Show prompt
        print(f"  {DIM}Prompt {idx + 1}/{len(PROMPTS)} ({remaining} remaining){RESET}")
        print(f"  Style: {color}{BOLD}{style}{RESET}  |  Language: {lang}")
        print(f"  {color}\"{text}\"{RESET}")
        print()

        while True:
            action = input(f"  {BOLD}[Enter]{RESET} record  |  {BOLD}[s]{RESET}kip  |  {BOLD}[r]{RESET}e-record  |  {BOLD}[p]{RESET}layback  |  {BOLD}[q]{RESET}uit > ").strip().lower()

            if action == "q":
                print(f"\n  Progress saved! You recorded {len(completed_set)}/{len(PROMPTS)} prompts ({format_duration(total_duration)}).")
                save_progress(progress_file, {
                    "completed": list(completed_set),
                    "total_duration_seconds": total_duration,
                })
                return

            elif action == "s":
                print(f"  {DIM}Skipped.{RESET}\n")
                break

            elif action == "p":
                if last_audio is not None:
                    print(f"  {DIM}Playing back...{RESET}")
                    play_audio(last_audio)
                else:
                    print(f"  {DIM}Nothing to play yet.{RESET}")
                continue

            elif action == "r":
                if last_filepath is not None and last_filepath.exists():
                    # Remove the last recording and re-record
                    last_filepath.unlink()
                    if (idx - 1) in completed_set or idx in completed_set:
                        # Undo the last completed one
                        target = idx if idx in completed_set else idx - 1
                        completed_set.discard(target)
                    print(f"  {DIM}Previous recording deleted. Recording again...{RESET}")
                else:
                    print(f"  {DIM}No previous recording to redo. Recording fresh...{RESET}")

                # Fall through to record
                action = ""

            if action == "" or action == "r":
                # Record
                print(f"  {BOLD}Speak now...{RESET}")
                audio = record_clip(
                    max_seconds=20.0,
                    silence_threshold=silence_threshold,
                    silence_duration=1.5,
                )

                if len(audio) == 0:
                    print(f"  {DIM}No audio detected. Try again.{RESET}")
                    continue

                # Trim silence
                trimmed = trim_silence(audio, silence_threshold)
                duration = len(trimmed) / SAMPLE_RATE

                if duration < 0.5:
                    print(f"  {DIM}Clip too short ({duration:.1f}s). Try again.{RESET}")
                    continue

                # Save
                filename = f"clip_{idx:04d}_{style}_{lang.replace('-', '')}.wav"
                filepath = base_dir / filename
                save_wav(trimmed, filepath)

                last_audio = trimmed
                last_filepath = filepath

                # Update progress
                completed_set.add(idx)
                total_duration += duration

                # Show encouragement
                encouragement = ENCOURAGEMENTS[enc_idx % len(ENCOURAGEMENTS)]
                enc_idx += 1
                random.shuffle(ENCOURAGEMENTS)

                print(f"  Saved: {filename} ({duration:.1f}s)")
                print(f"  {BOLD}{encouragement}{RESET}")

                # Milestone messages
                n = len(completed_set)
                if n == 10:
                    print(f"\n  {BOLD}  10 down! You're warming up. The voice model is starting to know you.{RESET}\n")
                elif n == 50:
                    print(f"\n  {BOLD}  50 clips! Quarter way there. Your voice clone is taking shape.{RESET}\n")
                elif n == 100:
                    print(f"\n  {BOLD}  HUNDRED! Halfway! At this point the model has your vibe.{RESET}\n")
                elif n == 150:
                    print(f"\n  {BOLD}  150! Almost there. The model can probably do your accent already.{RESET}\n")
                elif n == 200:
                    print(f"\n  {BOLD}  200!! Done! Your voice clone awaits. Run transcribe.py next!{RESET}\n")
                elif n % 25 == 0:
                    show_progress_bar(n, len(PROMPTS), total_duration)

                # Auto-save progress every 5 clips
                if n % 5 == 0:
                    save_progress(progress_file, {
                        "completed": list(completed_set),
                        "total_duration_seconds": total_duration,
                    })

                break

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"  Recording session complete!")
    print(f"  Clips recorded: {len(completed_set)}/{len(PROMPTS)}")
    print(f"  Total audio: {format_duration(total_duration)}")
    print(f"  Output: {base_dir}")
    print(f"\n  Next step: python transcribe.py --recordings-dir {base_dir}")
    print(f"{'=' * 60}\n")

    save_progress(progress_file, {
        "completed": list(completed_set),
        "total_duration_seconds": total_duration,
    })


if __name__ == "__main__":
    main()
