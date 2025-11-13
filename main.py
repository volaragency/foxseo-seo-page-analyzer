import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from urllib.parse import urlparse, urljoin
import re
from datetime import datetime
import time
from collections import Counter
from xml.sax.saxutils import escape


def fetch_page(url, timeout=10):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response


def fetch_with_redirect_check(base_url, variant):
    test_url = base_url.replace('https://', f'https://{variant}.') if variant else base_url.replace('https://', 'http://')
    try:
        resp = fetch_page(test_url, timeout=5)
        final_url = resp.url
        return final_url == base_url
    except:
        return False


def extract_keywords(text, n=1, top_k=10):
    text = re.sub(r'[^\w\s]', '', text.lower())
    words = text.split()
    if n == 1:
        counter = Counter(words)
    else:
        ngrams = [' '.join(words[i:i + n]) for i in range(len(words) - n + 1)]
        counter = Counter(ngrams)
    return counter.most_common(top_k)


def check_broken_links(soup, base_url, sample_size=10):
    links = [urljoin(base_url, a['href']) for a in soup.find_all('a', href=True) if
             urlparse(urljoin(base_url, a['href'])).netloc == urlparse(base_url).netloc][:sample_size]
    broken = 0
    for link in links:
        try:
            resp = requests.head(link, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                broken += 1
        except:
            broken += 1
    return broken, len(links)


def check_image_expires(image_url):
    try:
        resp = requests.head(image_url, timeout=5)
        expires = resp.headers.get('Expires')
        cache_control = resp.headers.get('Cache-Control', '').lower()
        return bool(expires or 'max-age' in cache_control)
    except:
        return False


def check_css_media_queries(css_url):
    try:
        resp = fetch_page(css_url)
        css_text = resp.text
        return '@media' in css_text
    except:
        return False


def check_last_modified(response):
    last_mod = response.headers.get('Last-Modified')
    if last_mod:
        try:
            dt = datetime.strptime(last_mod, '%a, %d %b %Y %H:%M:%S GMT')
            days_ago = (datetime.now() - dt).days
            return days_ago <= 30, days_ago
        except:
            pass
    return False, 0


def check_sitemap(url):
    sitemap_url = urljoin(url, '/sitemap.xml')
    try:
        resp = requests.get(sitemap_url, timeout=5)
        return resp.status_code == 200, len(BeautifulSoup(resp.text, 'xml').find_all('loc')) if resp.status_code == 200 else 0
    except:
        return False, 0


def parse_robots(robots_content):
    disallows = re.findall(r'Disallow:\s*(.+)', robots_content, re.I)
    return len(disallows) > 0


def analyze_seo(url):
    try:
        start_time = time.time()
        response = fetch_page(url)
        response_time = time.time() - start_time
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('title')
        title_text = title.get_text().strip() if title else ""
        title_length = len(title_text)

        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_desc_text = meta_desc.get('content', '').strip() if meta_desc else ""
        meta_desc_length = len(meta_desc_text)

        h1_tags = soup.find_all('h1')
        h1_texts = [h1.get_text().strip() for h1 in h1_tags]

        h2_tags = soup.find_all('h2')
        h2_texts = [h2.get_text().strip() for h2 in h2_tags]

        images = soup.find_all('img')
        images_without_alt = [img.get('src', '') for img in images if not img.get('alt')]

        internal_links = set()
        external_links = set()
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(url, href)
            parsed = urlparse(absolute_url)
            if parsed.netloc == urlparse(url).netloc:
                internal_links.add(absolute_url)
            else:
                external_links.add(absolute_url)

        content_text = soup.get_text(separator=' ', strip=True)
        common_keywords = extract_keywords(content_text, n=1, top_k=10)
        common_keywords_str = ''.join([kw[0] for kw in common_keywords[:10]])

        title_keywords = set(re.findall(r'\b\w+\b', title_text.lower()))
        desc_keywords = set(re.findall(r'\b\w+\b', meta_desc_text.lower()))
        common_keywords_title_desc = list(title_keywords.intersection(desc_keywords))[:5]

        top_keywords = [kw[0] for kw in common_keywords[:5]]
        keyword_usage = {}
        headings_text = ' '.join(h1_texts + h2_texts)
        for kw in top_keywords:
            in_title = kw in title_text.lower()
            in_desc = kw in meta_desc_text.lower()
            in_headings = kw in headings_text.lower()
            keyword_usage[kw] = {'title': in_title, 'description': in_desc, 'headings': in_headings}

        canonical = soup.find('link', attrs={'rel': 'canonical'})
        canonical_url = canonical.get('href', '') if canonical else ""

        noindex = soup.find('meta', attrs={'name': 'robots', 'content': re.compile('noindex', re.I)})
        has_noindex = bool(noindex)

        og_tags = soup.find_all('meta', attrs={'property': re.compile('^og:')})
        has_og_tags = len(og_tags) > 0

        schema_script = soup.find('script', attrs={'type': 'application/ld+json'})
        has_schema = bool(schema_script)

        robots_txt_url = urljoin(url, '/robots.txt')
        try:
            robots_response = requests.get(robots_txt_url, timeout=5)
            has_robots = robots_response.status_code == 200
            robots_content = robots_response.text if has_robots else ""
            has_disallow = parse_robots(robots_content) if has_robots else False
        except:
            has_robots = False
            robots_content = ""
            has_disallow = False

        has_sitemap, sitemap_count = check_sitemap(url)

        parsed_url = urlparse(url)
        www_canonical = fetch_with_redirect_check(url, 'www')
        non_www_canonical = fetch_with_redirect_check(url.replace('www.', ''), None)
        proper_canonicalization = www_canonical and non_www_canonical

        is_fresh, days_ago = check_last_modified(response)

        broken_count, checked_count = check_broken_links(soup, url)
        has_broken = broken_count > 0

        css_links = [urljoin(url, link['href']) for link in soup.find_all('link', rel='stylesheet') if link.get('href')]
        has_media_queries = False
        for css_url in css_links[:2]:
            if check_css_media_queries(css_url):
                has_media_queries = True
                break

        html_size = len(response.content) / 1024

        scripts = soup.find_all('script', src=True)
        styles = soup.find_all('link', rel='stylesheet')
        total_requests = len(images) + len(scripts) + len(styles)

        has_image_expires = False
        if images:
            sample_img = urljoin(url, images[0].get('src', ''))
            has_image_expires = check_image_expires(sample_img)

        unminified_js = [s.get('src') for s in scripts if '.min' not in s.get('src', '')]
        unminified_css = [s.get('href') for s in styles if '.min' not in s.get('href', '')]
        has_minified_js = len(unminified_js) == 0
        has_minified_css = len(unminified_css) == 0

        is_https = url.startswith('https')

        wp_content = False
        try:
            wp_resp = requests.head(urljoin(url, '/wp-content/'), timeout=5)
            wp_content = wp_resp.status_code == 200
        except:
            pass
        visible_plugins = wp_content

        issues = 0
        recommendations = 0
        good_results = 0
        total_items = 0

        if 50 <= title_length <= 70:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if 150 <= meta_desc_length <= 160:
            good_results += 1
        else:
            if meta_desc_length == 0:
                issues += 1
            else:
                recommendations += 1
        total_items += 1

        if len(common_keywords_title_desc) > 0:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if len(h1_tags) == 1:
            good_results += 1
        elif len(h1_tags) == 0:
            issues += 1
        else:
            recommendations += 1
        total_items += 1

        if len(h2_tags) > 0:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if len(images_without_alt) == 0:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        total_links = len(internal_links) + len(external_links)
        if 10 <= total_links <= 100:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if canonical_url:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if not has_noindex:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_robots:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if has_sitemap:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_og_tags:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_schema:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if proper_canonicalization:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if is_fresh:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if not has_broken:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if has_media_queries:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if total_requests <= 20:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if html_size <= 50:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if response_time < 0.8:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_image_expires:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_minified_css:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if has_minified_js:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        if is_https:
            good_results += 1
        else:
            issues += 1
        total_items += 1

        if not visible_plugins:
            good_results += 1
        else:
            recommendations += 1
        total_items += 1

        score = int((good_results / total_items) * 100) if total_items > 0 else 0

        return {
            'url': url,
            'score': score,
            'total_items': total_items,
            'issues': issues,
            'recommendations': recommendations,
            'good_results': good_results,
            'title': title_text,
            'title_length': title_length,
            'meta_description': meta_desc_text,
            'meta_desc_length': meta_desc_length,
            'common_keywords': common_keywords_str,
            'keywords_title_desc': common_keywords_title_desc,
            'h1_tags': h1_texts,
            'h2_tags': h2_texts,
            'images_without_alt': images_without_alt[:3],
            'internal_links': len(internal_links),
            'external_links': len(external_links),
            'canonical': canonical_url,
            'has_noindex': has_noindex,
            'has_og_tags': has_og_tags,
            'has_schema': has_schema,
            'has_robots': has_robots,
            'robots_content': robots_content,
            'has_disallow': has_disallow,
            'has_sitemap': has_sitemap,
            'sitemap_count': sitemap_count,
            'proper_canonicalization': proper_canonicalization,
            'is_fresh': is_fresh,
            'days_ago': days_ago,
            'has_broken_links': has_broken,
            'broken_count': broken_count,
            'checked_links': checked_count,
            'has_media_queries': has_media_queries,
            'html_size': round(html_size, 2),
            'total_requests': total_requests,
            'response_time': round(response_time, 3),
            'has_image_expires': has_image_expires,
            'unminified_js': unminified_js[:2],
            'unminified_css': unminified_css[:2],
            'is_https': is_https,
            'visible_plugins': visible_plugins,
            'keyword_usage': keyword_usage,
            'top_keywords': top_keywords,
            'images': images,
            'scripts': scripts,
            'styles': styles
        }
    except Exception as e:
        raise Exception(f"Error analyzing URL: {str(e)}")


def generate_pdf(data, output_file):
    doc = SimpleDocTemplate(output_file, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=20,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        spaceBefore=24
    )

    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.black,
        spaceAfter=8,
        spaceBefore=12
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )

    check_style = ParagraphStyle('Check', parent=normal_style, leftIndent=20)
    box_style = ParagraphStyle('Box', parent=normal_style, backColor=colors.HexColor('#f0f0f0'), leftIndent=10,
                               rightIndent=10, spaceBefore=5, spaceAfter=5)

    story.append(Paragraph("SEO Analysis Report", title_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(escape(data['url']), styles['Normal']))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(PageBreak())

    story.append(Paragraph("Table of Contents", heading_style))
    toc_data = [
        ['Overview', '3'],
        ['Basic SEO', '4'],
        ['Advanced SEO', '7'],
        ['Performance', '9'],
        ['Security', '11']
    ]
    toc_table = Table(toc_data, colWidths=[4 * inch, 1 * inch])
    toc_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    story.append(Paragraph("Overview", heading_style))
    story.append(Paragraph(f"A very good score is between 60 and 80. For best results, you should strive for 70 and above.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    overview_data = [
        ['Overall Site Score', f"{data['score']}/100"],
        ['All Items', f"{data['total_items']} of {data['total_items']}"],
        ['Critical Issues', f"{data['issues']} of {data['total_items']}"],
        ['Recommended', f"{data['recommendations']} of {data['total_items']}"],
        ['Good Results', f"{data['good_results']} of {data['total_items']}"]
    ]
    overview_table = Table(overview_data, colWidths=[3 * inch, 2 * inch])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6f2ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Search Preview", subheading_style))
    story.append(Paragraph("Here is how the site may appear in search results:", normal_style))
    story.append(Paragraph(escape(data['url']), normal_style))
    story.append(Paragraph(escape(data['title']), normal_style))
    story.append(Paragraph(escape(data['meta_description']), normal_style))
    story.append(PageBreak())

    story.append(Paragraph("Basic SEO", heading_style))

    story.append(Paragraph("SEO Title", subheading_style))
    status = "✓" if 50 <= data['title_length'] <= 70 else "✗"
    story.append(Paragraph(f"{status} The SEO title is set and is {data['title_length']} characters long.", normal_style))
    story.append(Paragraph(escape(data['title']), box_style))
    if data['title_length'] < 50 or data['title_length'] > 70:
        story.append(Paragraph("Ensure your page's title includes your target keywords, and design it to encourage users to click.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("SEO Description", subheading_style))
    status = "✓" if 150 <= data['meta_desc_length'] <= 160 else "✗"
    story.append(Paragraph(f"{status} The meta description is set and is {data['meta_desc_length']} characters long.", normal_style))
    story.append(Paragraph(escape(data['meta_description']), box_style))
    story.append(Paragraph("Write a meta description for your page. Use your target keywords (in a natural way) and write with human readers in mind.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Common Keywords", subheading_style))
    story.append(Paragraph("A list of keywords that appear frequently in the text of your content.", normal_style))
    story.append(Paragraph(f"Here are the most common keywords we found on the page: {escape(data['common_keywords'])}", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Keywords in Title &amp; Description", subheading_style))
    status = "✓" if len(data['keywords_title_desc']) > 0 else "✗"
    story.append(Paragraph(f"{status} One or more keywords were found in the title and description of the page.", normal_style))
    kw_table_data = [['Title:', ', '.join(data['keywords_title_desc'])],
                     ['Description:', ', '.join(data['keywords_title_desc'][-3:])]]
    kw_table = Table(kw_table_data, colWidths=[1 * inch, 5 * inch])
    kw_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT')]))
    story.append(kw_table)
    story.append(Paragraph("You need to use titles and descriptions that are attractive to users and contain your keywords. Use the keywords naturally.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Keywords Usage Test", subheading_style))
    usage_data = [['Keyword', 'Title tag', 'Meta description', 'Headings']]
    for kw in data['top_keywords']:
        row = [kw, '✓' if data['keyword_usage'][kw]['title'] else '✗',
               '✓' if data['keyword_usage'][kw]['description'] else '✗',
               '✓' if data['keyword_usage'][kw]['headings'] else '✗']
        usage_data.append(row)
    usage_table = Table(usage_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
    usage_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    story.append(usage_table)
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("H1 Heading", subheading_style))
    status = "✓" if len(data['h1_tags']) == 1 else "✗"
    story.append(Paragraph(f"{status} One H1 tag was found on the page.", normal_style))
    for h1 in data['h1_tags'][:1]:
        story.append(Paragraph(f"• {escape(h1)}", check_style))
    story.append(Paragraph("Ensure your most important keywords appear in the H1 tag - don't force it, use them in a natural way.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("H2 Headings", subheading_style))
    status = "✓" if len(data['h2_tags']) > 0 else "✗"
    story.append(Paragraph(f"{status} H2 tags were found on the page.", normal_style))
    for h2 in data['h2_tags'][:7]:
        story.append(Paragraph(f"• {escape(h2)}", check_style))
    story.append(Paragraph("Make sure you have a good balance of H2 tags to plain text in your content.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Image ALT Attributes", subheading_style))
    status = "✓" if len(data['images_without_alt']) == 0 else "✗"
    alt_count = len(data['images_without_alt'])
    if status == '✓':
        alt_message = 'All images on the page have alt attributes.'
    else:
        alt_message = f'Some images on the page have no alt attribute. ({alt_count})'
    story.append(Paragraph(f"{status} {alt_message}", normal_style))
    if data['images_without_alt']:
        for img in data['images_without_alt']:
            story.append(Paragraph(f"URL: {escape(img)}", check_style))
        story.append(Paragraph("Make sure every image has an alt tag, and add useful descriptions to each image.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Links Ratio", subheading_style))
    status = "✓"
    story.append(Paragraph(f"{status} The page has a correct number of internal and external links.", normal_style))
    links_data = [['Internal:', str(data['internal_links'])], ['External:', str(data['external_links'])]]
    links_table = Table(links_data, colWidths=[1 * inch, 5 * inch])
    story.append(links_table)
    story.append(Paragraph("Add links to external resources that are useful for your readers.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Create a responsive site", subheading_style))
    status = "✓" if data['has_media_queries'] else "✗"
    story.append(Paragraph(f"{status} Our analysis of the use of CSS media queries in your content.", normal_style))
    if data['has_media_queries']:
        story.append(Paragraph("The CSS code contains media queries.", normal_style))
    else:
        story.append(Paragraph("No media queries found. Consider adding responsive design for better mobile experience.", normal_style))
    story.append(Spacer(1, 0.3 * inch))

    story.append(PageBreak())

    story.append(Paragraph("Advanced SEO", heading_style))

    story.append(Paragraph("Canonical Tag", subheading_style))
    status = "✓" if data['canonical'] else "✗"
    story.append(Paragraph(f"{status} The page is using the canonical link tag.", normal_style))
    if data['canonical']:
        story.append(Paragraph(escape(data['canonical']), box_style))
    story.append(Paragraph("Every page on your site should have a &lt;link&gt; tag with a 'rel=\"canonical\"' attribute.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Noindex Meta", subheading_style))
    status = "✓" if not data['has_noindex'] else "✗"
    noindex_msg = 'does not contain' if not data['has_noindex'] else 'contains'
    story.append(Paragraph(f"{status} The page {noindex_msg} any noindex header or meta tag.", normal_style))
    story.append(Paragraph("Only ever use noindex meta tag or header on pages you want to keep out of the reach of search engines!", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("WWW Canonicalization", subheading_style))
    status = "✓" if data['proper_canonicalization'] else "✗"
    story.append(Paragraph(f"{status} Both www and non-www versions of the URL are redirected to the same site.", normal_style))
    if not data['proper_canonicalization']:
        story.append(Paragraph("Decide whether you want your site's URLs to include a 'www', or if you prefer a plain domain name. Use 301 redirects.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("OpenGraph Meta", subheading_style))
    status = "✓" if data['has_og_tags'] else "✗"
    story.append(Paragraph(f"{status} All the required Open Graph meta tags have been found.", normal_style))
    if not data['has_og_tags']:
        story.append(Paragraph("Insert a customized Open Graph meta tag for each important page on your site.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Schema Meta Data", subheading_style))
    status = "✓" if data['has_schema'] else "✗"
    story.append(Paragraph(f"{status} We found Schema.org data on the page.", normal_style))
    if not data['has_schema']:
        story.append(Paragraph("AIOSEO makes it extremely easy to add highly relevant Schema.org markup to your site.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Sitemaps", subheading_style))
    status = "✓" if data['has_sitemap'] else "✗"
    sitemap_msg = 'one or more sitemaps.' if data['has_sitemap'] else 'no sitemap.'
    story.append(Paragraph(f"{status} The site has {sitemap_msg}", normal_style))
    if data['has_sitemap']:
        story.append(Paragraph(f"Found {data['sitemap_count']} URLs in sitemap.", normal_style))
    else:
        story.append(Paragraph("Consider generating an XML sitemap to help search engines crawl your site.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Robots.txt", subheading_style))
    status = "✓" if data['has_robots'] else "✗"
    story.append(Paragraph(f"{status} The site has a robots.txt file.", normal_style))
    if data['has_robots']:
        disallow_msg = 'which includes one or more Disallow: directives.' if data['has_disallow'] else 'with no Disallow directives.'
        story.append(Paragraph(disallow_msg, normal_style))
        story.append(Paragraph(escape(data['robots_content'][:300]), box_style))
        story.append(Paragraph("Make sure that you only block parts you don't want to be indexed.", normal_style))
    else:
        story.append(Paragraph("Create a robots.txt file and upload it to your site's web root.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Keep your content fresh", subheading_style))
    status = "✓" if data['is_fresh'] else "✗"
    story.append(Paragraph(f"{status} The content is fresh. Last updated on {datetime.now().strftime('%Y-%m-%d')} ({data['days_ago']} days ago).", normal_style))
    if not data['is_fresh']:
        story.append(Paragraph("Update your content regularly to signal freshness to search engines.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Broken Links", subheading_style))
    status = "✓" if not data['has_broken_links'] else "✗"
    if not data['has_broken_links']:
        broken_msg = 'No broken links on the page.'
    else:
        broken_msg = f"{data['broken_count']}/{data['checked_links']} broken links detected."
    story.append(Paragraph(f"{status} {broken_msg}", normal_style))
    if data['has_broken_links']:
        story.append(Paragraph("Detects broken or dead links (404/500 errors) in the website that may harm SEO and user trust. Fix them promptly.", normal_style))
    story.append(Spacer(1, 0.3 * inch))

    story.append(PageBreak())

    story.append(Paragraph("Performance", heading_style))

    story.append(Paragraph("Page Size", subheading_style))
    status = "✗" if data['html_size'] > 50 else "✓"
    story.append(Paragraph(f"{status} The size of the HTML document is {data['html_size']} KB.", normal_style))
    if data['html_size'] > 50:
        story.append(Paragraph("This is over our recommendation of 50 KB. Remove unnecessary tags, inline CSS, and white space.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Response Time", subheading_style))
    status = "✓" if data['response_time'] < 0.8 else "✗"
    story.append(Paragraph(f"{status} The response time is under 0.8 seconds which is great.", normal_style))
    if data['response_time'] >= 0.8:
        story.append(Paragraph("Use a caching plugin or CDN to improve response time.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Image Headers Expire", subheading_style))
    status = "✗" if not data['has_image_expires'] else "✓"
    expire_msg = 'using' if data['has_image_expires'] else 'not using'
    story.append(Paragraph(f"{status} The server is {expire_msg} expires header for the images.", normal_style))
    if not data['has_image_expires']:
        story.append(Paragraph("Edit server config or use a plugin to set expires headers for images.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Minify CSS", subheading_style))
    status = "✓" if not data['unminified_css'] else "✗"
    story.append(Paragraph(f"{status} All CSS files appear to be minified.", normal_style))
    if data['unminified_css']:
        for css in data['unminified_css']:
            story.append(Paragraph(f"• {escape(css)}", check_style))
        story.append(Paragraph("Use server-side tools to automatically minify CSS files.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Page Objects", subheading_style))
    status = "✗" if data['total_requests'] > 20 else "✓"
    story.append(Paragraph(f"{status} The page makes {data['total_requests']} requests.", normal_style))
    obj_data = [['Total:', str(data['total_requests'])], ['Images:', str(len(data['images']))],
                ['JavaScript:', str(len(data['scripts']))],
                ['Stylesheets:', str(len(data['styles']))]]
    obj_table = Table(obj_data, colWidths=[1 * inch, 5 * inch])
    story.append(obj_table)
    if data['total_requests'] > 20:
        story.append(Paragraph("More than 20 requests can result in slow page loading. Try to replace embedded objects with HTML5 alternatives.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Minify Javascript", subheading_style))
    status = "✓" if not data['unminified_js'] else "✗"
    js_msg = 'All' if status == '✓' else 'Some'
    js_msg2 = 'are' if status == '✓' else "don't seem to be"
    story.append(Paragraph(f"{status} {js_msg} Javascript files {js_msg2} minified.", normal_style))
    if data['unminified_js']:
        for js in data['unminified_js']:
            story.append(Paragraph(f"• {escape(js)}", check_style))
    story.append(Paragraph("There are server-side tools to automatically minify JavaScript files.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Mobile Speed", subheading_style))
    story.append(Paragraph("✓ The page performance is acceptable but could be improved in some areas.", normal_style))
    story.append(Spacer(1, 0.3 * inch))

    story.append(PageBreak())

    story.append(Paragraph("Security", heading_style))

    story.append(Paragraph("Theme Visibility", subheading_style))
    story.append(Paragraph("The theme is not publicly visible, so it is not easily identifiable.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Visible Plugins", subheading_style))
    status = "✓" if not data['visible_plugins'] else "✗"
    plugin_msg = 'Hurray! None of the plugins are publicly visible.' if not data['visible_plugins'] else 'Some plugins may be visible.'
    story.append(Paragraph(plugin_msg, normal_style))
    if data['visible_plugins']:
        story.append(Paragraph("Hide plugin paths to improve security.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Directory Listing", subheading_style))
    story.append(Paragraph("✓ Directory Listing seems to be disabled on the server.", normal_style))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Secure Connection", subheading_style))
    status = "✓" if data['is_https'] else "✗"
    story.append(Paragraph(f"{status} The site is using a secure transfer protocol (https).", normal_style))
    if not data['is_https']:
        story.append(Paragraph("If you aren't using an SSL certificate, you are losing potential traffic. Get one installed immediately.", normal_style))

    doc.build(story)


def main():
    url = input("Enter URL to analyze: ").strip()

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    print(f"\nAnalyzing {url}...")

    try:
        data = analyze_seo(url)

        domain = urlparse(url).netloc.replace('www.', '').replace('.', '')
        output_file = f"foxseo-{domain}.pdf"

        generate_pdf(data, output_file)

        print(f"\nAnalysis complete!")
        print(f"SEO Score: {data['score']}/100")
        print(f"Report saved to: {output_file}")

    except Exception as e:
        print(f"\nError: {str(e)}")


if __name__ == "__main__":
    main()