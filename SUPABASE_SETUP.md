# Supabase Setup for Flask Webhook Server

## 🗄️ **Database Setup**

### **Step 1: Create Tables in Supabase**

1. **Go to your Supabase project dashboard**
2. **Navigate to SQL Editor**
3. **Run the SQL script**: `setup_supabase_tables.sql`

This will create:
- **`contacts` table**: Stores contact information
- **`messages` table**: Stores message content linked to contacts

### **Step 2: Table Structure**

#### **Contacts Table**
```sql
- contact_id (TEXT, UNIQUE) - Primary identifier from GHL
- first_name (TEXT) - Contact's first name
- last_name (TEXT) - Contact's last name
- phone (TEXT) - Contact's phone number
- email (TEXT) - Contact's email address
- company_name (TEXT) - Company name
- created_at (TIMESTAMP) - When record was created
- updated_at (TIMESTAMP) - When record was last updated
```

#### **Messages Table**
```sql
- contact_id (TEXT) - Links to contacts table
- message_body (TEXT) - Content of the message
- message_type (TEXT) - Type of message (SMS, email, etc.)
- created_at (TIMESTAMP) - When message was received
```

## 🔄 **How It Works**

### **Webhook Flow**
1. **GoHighLevel sends webhook** to your Flask server
2. **Flask server extracts** contact_id, first_name, last_name, phone, email, company_name
3. **Contact data stored** in `contacts` table
4. **Message data stored** in `messages` table
5. **Response sent back** to GoHighLevel

### **Data Mapping**
From your webhook example:
```json
{
  "contact_id": "LlRy0ogwXYU63KveELfD",
  "first_name": "John",
  "last_name": "ElstadTest",
  "phone": "+15036801842",
  "email": "flateye0@gmail.com",
  "company_name": "Test Solutions",
  "message": {
    "body": "Testing testing testing",
    "type": 2
  }
}
```

## 🧪 **Testing**

### **1. Send Another Webhook**
Trigger your GoHighLevel workflow again to test the new functionality.

### **2. Check Supabase Tables**
- Go to **Table Editor** in Supabase
- Check both `contacts` and `messages` tables
- Verify data is being stored correctly

### **3. Check Flask Logs**
Look for these log messages:
```
INFO:webhook_handlers:Contact LlRy0ogwXYU63KveELfD stored in Supabase successfully
INFO:webhook_handlers:Message for contact LlRy0ogwXYU63KveELfD stored in Supabase successfully
```

## 🔧 **Troubleshooting**

### **Common Issues**

1. **"Supabase credentials not configured"**
   - Check your `.env` file has correct SUPABASE_URL and SUPABASE_ANON_KEY

2. **"Failed to store contact in Supabase"**
   - Verify tables exist in Supabase
   - Check RLS policies allow insert operations
   - Verify API key has proper permissions

3. **"Foreign key constraint failed"**
   - Ensure contacts table is created before messages table
   - Check that contact_id exists in contacts before inserting messages

### **Debug Steps**

1. **Check `/config` endpoint** to verify Supabase credentials
2. **Review Flask server logs** for detailed error messages
3. **Test Supabase connection** manually in SQL Editor
4. **Verify table permissions** and RLS policies

## 🚀 **Next Steps**

After successful setup:
1. **Customize the data mapping** if needed
2. **Add business logic** for processing webhooks
3. **Set up additional webhook triggers** in GoHighLevel
4. **Create views or queries** for analyzing the data
5. **Set up notifications** for new contacts/messages

## 📊 **Sample Queries**

### **Get All Contacts with Message Count**
```sql
SELECT 
    c.*,
    COUNT(m.id) as message_count
FROM contacts c
LEFT JOIN messages m ON c.contact_id = m.contact_id
GROUP BY c.id, c.contact_id, c.first_name, c.last_name, c.phone, c.email, c.company_name, c.created_at, c.updated_at
ORDER BY c.created_at DESC;
```

### **Get Recent Messages**
```sql
SELECT 
    m.*,
    c.first_name,
    c.last_name,
    c.company_name
FROM messages m
JOIN contacts c ON m.contact_id = c.contact_id
ORDER BY m.created_at DESC
LIMIT 10;
```
