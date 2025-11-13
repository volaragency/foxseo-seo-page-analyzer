## SEO Page Analyzer

A comprehensive, Python-based tool designed to perform in-depth on-page SEO, performance, and security audits of any public website, culminating in a detailed, multi-page **PDF report**.

The generated PDF report provides a concise **Overall Site Score** out of 100 and categorizes checks into Critical Issues, Recommended improvements, and Good Results. The output includes a **Search Preview** of how the page may appear in Google and uses clear checkmarks (✓) and crosses (✗) to indicate the status of each audit item across sections like Basic SEO, Advanced SEO, Performance, and Security.

## Features

The tool performs a holistic analysis to provide a complete picture of a webpage's health, calculates an overall score, and highlights critical issues and recommendations.

### **Basic SEO & Content Analysis**

* **SEO Title & Description Check:** Validates the length and presence of the Title and Meta Description tags.  
* **Keyword Analysis:** Identifies the top 10 most frequent single-word keywords and checks if the top 5 are used in the Title, Description, and Headings.  
* **Heading Structure:** Checks for the presence of a single `H1` tag and ensures `H2` tags are present.  
* **Image ALT Attributes:** Scans for images missing the required `alt` attribute.  
* **Links Ratio:** Reports the count of internal and external links found on the page.  
* **Responsive Design:** Analyzes external CSS files for the presence of `@media` queries to check for mobile-friendliness.

### **Advanced SEO & Technical Checks**

* **Canonical Tag:** Confirms the use of the `rel="canonical"` link tag to prevent duplicate content issues.  
* **Noindex Meta:** Checks for the presence of a `noindex` meta tag or header.  
* **WWW Canonicalization:** Verifies that both the `www` and non-`www` versions of the URL redirect properly to the desired site version (using 301 redirects).  
* **OpenGraph & Schema Data:** Checks for **OpenGraph** (`og:`) tags (for social media sharing) and **Schema.org** (`application/ld+json`) data.  
* **Sitemaps & Robots:** Verifies the presence of `robots.txt` and `sitemap.xml`, including the number of URLs found in the sitemap.  
* **Content Freshness:** Reports the age of the content based on the server's `Last-Modified` header.  
* **Broken Links:** Checks a sample of internal links for 4xx/5xx errors.

### **Performance Analysis**

* **Response Time:** Measures the server response time against a threshold of 0.8 seconds.  
* **Page Size:** Reports the HTML document size (in KB) and flags it if it exceeds the recommended limit of 50 KB.  
* **Page Objects/Requests:** Counts the total number of requests for images, JavaScript, and Stylesheets, flagging the page if the total exceeds 20\.  
* **Caching/Headers:** Checks for the presence of `Expires` or `Cache-Control` headers for images.  
* **Minification:** Checks if CSS and JavaScript files appear to be minified (by looking for `.min` in the filename).

### **Security Checks**

* **Secure Connection:** Confirms the use of **HTTPS**.  
* **Plugin Visibility:** Checks for publicly visible paths, such as the `/wp-content/` directory, to assess potential security risks from identifiable CMS plugins.  
* **Directory Listing:** Confirmed to be disabled on the server.


## **Installation and Dependencies**

The project is written in Python and uses the following third-party libraries.

### **Prerequisites**

* **Python 3.x**

### **Installation**

1. **Clone the repository** (or download `main.py` and `requirements.txt`).  
2. **Install dependencies** using the provided `requirements.txt` file:

```Bash

pip install -r requirements.txt
```
*(Dependencies include `requests`, `beautifulsoup4`, and `reportlab`)*.

---

## **How to Run**

1. Open your terminal or command prompt.  
2. Navigate to the directory containing `main.py`.  
3. Execute the script and follow the prompt:

```Bash

python main.py
```
4. When prompted, **Enter URL to analyze** (e.g., `https://example.com/`). The script will then run the analysis, grade the site, and generate the report.

### **Output**

A PDF report file will be saved in the same directory, named based on the domain (e.g., `foxseo-yourdomain.pdf`).

## **License**

This project is released under the MIT License. You may freely use, modify, and distribute it with attribution.

## Author

[**Volar Agency**](https://thevolar.com)

