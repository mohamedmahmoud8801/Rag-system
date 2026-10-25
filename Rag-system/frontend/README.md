# RAG System: الواجهة (React + Vite + TypeScript + Tailwind)

## المطلوب
- **Node.js 20.19 أو أحدث (أو 22+)**: اتأكد بـ `node -v`
- الباك إند شغّال على بورت 8000 ومعاه نظام الـ auth (`auth_system.zip`)

## المكان
فك الـ zip بحيث فولدر `frontend/` يبقى **جنب** فولدر `src/`:
```
Rag-system/Rag-system/
├── src/
└── frontend/      <- هنا
```

## التشغيل (terminal لكل واحد)
```bash
# 1) الباك إند (زي ما بتشغّله)
cd ~/Desktop/Rag-system/Rag-system/src
uvicorn main:app --reload --port 8000

# 2) الواجهة
cd ~/Desktop/Rag-system/Rag-system/frontend
npm install
npm run dev
```
افتح **http://localhost:5173**

- الباك إند على بورت تاني؟ انسخ `.env.example` باسم `.env` وغيّر `VITE_BACKEND_URL`.
- الواجهة بتكلّم الباك إند عن طريق proxy، فمش محتاج تعدّل CORS في التطوير.

## أول مرة
1. حط إيميلك في `.env` بتاع الباك إند: `AUTH_ADMIN_IDENTIFIERS="you@gmail.com"` (يبقى admin).
2. من الواجهة: **Create account** وسجّل بنفس الإيميل أو برقم تليفونك.
3. الكود بيوصل على الإيميل لو `AUTH_EMAIL_DELIVERY="smtp"`. ولو `console` هتلاقيه مطبوع في الـ terminal بتاع الباك إند.

## اللي شغّال دلوقتي
- تسجيل، كود تحقق، دخول بالباسورد أو بكود، نسيت كلمة السر (إيميل أو تليفون)
- عربي/إنجليزي مع RTL، وبيتحفظ اختيارك
- Chat بالمصادر (بيستخدم `POST /api/v1/nlp/index/answer/{project_id}`)
- صفحة المستخدمين للـ admin فقط
- **لسه Placeholder**: Projects وKnowledge وVideo وData وEvaluation وSettings، والـ Dashboard من غير إحصائيات

## للـ Chat
- المشروع بيتحدد من الشريحة اللي فوق (**Project #1**). لازم ملفاته تكون اتعالجت واتفهرست.
- المحادثة بتتحفظ في المتصفح (لكل مستخدم ومشروع).
- في `src/routes/nlp.py` دالة `answer_rag` بتنادي `answer_rag_question` من غير `db_client`، فالـ neighbor expansion مقفول. ضيف `db_client=request.app.db_client` للنداء عشان يشتغل.

## Build للإنتاج
```bash
npm run build      # الناتج في dist/
```
قدّمه من نفس الدومين مع reverse proxy يوجّه `/api` للباك إند (أو فعّل CORS في الباك إند).
