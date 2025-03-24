from time import sleep
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
import unicodedata


class Tweet:
    def __init__(
        self,
        card: WebDriver,
        driver: WebDriver,
        actions: ActionChains,
        scrape_poster_details=False,
    ) -> None:
        self.card = card
        self.error = False
        self.tweet = None
        self.has_media = 0

        # Helper function to safely extract text with Arabic support
        def safe_extract_text(element):
            try:
                text = element.text
                return unicodedata.normalize('NFC', text)
            except:
                try:
                    return element.get_attribute('innerText') or element.get_attribute('textContent') or ""
                except:
                    return ""

        # Extract basic tweet info
        try:
            self.user = safe_extract_text(card.find_element("xpath", './/div[@data-testid="User-Name"]//span'))
        except NoSuchElementException:
            self.error = True
            self.user = "skip"

        try:
            self.handle = safe_extract_text(card.find_element("xpath", './/span[contains(text(), "@")]'))
        except NoSuchElementException:
            self.error = True
            self.handle = "skip"

        try:
            self.date_time = card.find_element("xpath", ".//time").get_attribute("datetime")
            self.is_ad = False if self.date_time else True
        except NoSuchElementException:
            self.is_ad = True
            self.error = True
            self.date_time = "skip"

        if self.error:
            return

        # Verification check
        try:
            card.find_element("xpath", './/*[local-name()="svg" and @data-testid="icon-verified"]')
            self.verified = True
        except NoSuchElementException:
            self.verified = False

        # Improved content extraction with Arabic support
        self.content = ""
        try:
            text_container = card.find_element("xpath", '(.//div[@data-testid="tweetText"])[1]')
            elements = text_container.find_elements("xpath", ".//*[self::span or self::a or self::img]")
            
            for element in elements:
                try:
                    if element.tag_name == "img" and "emoji" in element.get_attribute("src", ""):
                        self.content += element.get_attribute("alt", "")
                    else:
                        self.content += safe_extract_text(element)
                except:
                    continue
                    
            self.content = unicodedata.normalize('NFC', self.content.strip())
        except NoSuchElementException:
            self.content = ""

        # Engagement metrics
        metrics = {
            'reply_cnt': './/button[@data-testid="reply"]//span',
            'retweet_cnt': './/button[@data-testid="retweet"]//span',
            'like_cnt': './/button[@data-testid="like"]//span',
            'analytics_cnt': './/a[contains(@href, "/analytics")]//span'
        }
        
        for attr, xpath in metrics.items():
            try:
                value = safe_extract_text(card.find_element("xpath", xpath))
                setattr(self, attr, value if value else "0")
            except NoSuchElementException:
                setattr(self, attr, "0")

        # Tags and mentions
        try:
            self.tags = [safe_extract_text(tag) for tag in 
                        card.find_elements("xpath", './/a[contains(@href, "src=hashtag_click")]')]
        except NoSuchElementException:
            self.tags = []

        try:
            self.mentions = [safe_extract_text(mention) for mention in 
                           card.find_elements("xpath", '(.//div[@data-testid="tweetText"])[1]//a[contains(text(), "@")]')]
        except NoSuchElementException:
            self.mentions = []

        # Emojis
        try:
            self.emojis = [
                unicodedata.normalize('NFC', emoji.get_attribute("alt", ""))
                for emoji in card.find_elements("xpath", '(.//div[@data-testid="tweetText"])[1]/img[contains(@src, "emoji")]')
            ]
        except NoSuchElementException:
            self.emojis = []

        # Media and profile info
        try:
            self.profile_img = card.find_element(
                "xpath", './/div[@data-testid="Tweet-User-Avatar"]//img'
            ).get_attribute("src") or ""
        except NoSuchElementException:
            self.profile_img = ""

        try:
            self.tweet_link = card.find_element(
                "xpath", ".//a[contains(@href, '/status/')]"
            ).get_attribute("href") or ""
            self.tweet_id = str(self.tweet_link.split("/")[-1]) if self.tweet_link else ""
        except NoSuchElementException:
            self.tweet_link = ""
            self.tweet_id = ""

        # Media detection
        try:
            media_elements = card.find_elements(
                "xpath",
                '''
                .//div[@data-testid="tweetPhoto"] |
                .//div[@data-testid="videoPlayer"] |
                .//div[contains(@data-testid, "video")] |
                .//img[contains(@src, "twimg.com/media/")] |
                .//img[contains(@src, "ext_tw_video_thumb")] |
                .//video[contains(@src, "twimg.com")] |
                .//*[@data-testid="card.layoutLarge.media"] |
                .//*[@aria-label="Embedded image"] |
                .//*[@aria-label="Embedded video"]
                '''
            )
            self.has_media = 1 if media_elements else 0
        except Exception:
            self.has_media = 0

        # Poster details (if requested)
        self.following_cnt = "0"
        self.followers_cnt = "0"
        self.user_id = None

        if scrape_poster_details:
            el_name = card.find_element(
                "xpath", './/div[@data-testid="User-Name"]//span'
            )

            ext_hover_card = False
            ext_user_id = False
            ext_following = False
            ext_followers = False
            hover_attempt = 0

            while (
                not ext_hover_card
                or not ext_user_id
                or not ext_following
                or not ext_followers
            ):
                try:
                    actions.move_to_element(el_name).perform()

                    hover_card = driver.find_element(
                        "xpath", '//div[@data-testid="hoverCardParent"]'
                    )

                    ext_hover_card = True

                    while not ext_user_id:
                        try:
                            raw_user_id = hover_card.find_element(
                                "xpath",
                                '(.//div[contains(@data-testid, "-follow")]) | (.//div[contains(@data-testid, "-unfollow")])',
                            ).get_attribute("data-testid")

                            if raw_user_id == "":
                                self.user_id = None
                            else:
                                self.user_id = str(raw_user_id.split("-")[0])

                            ext_user_id = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return

                    while not ext_following:
                        try:
                            self.following_cnt = hover_card.find_element(
                                "xpath", './/a[contains(@href, "/following")]//span'
                            ).text

                            if self.following_cnt == "":
                                self.following_cnt = "0"

                            ext_following = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return

                    while not ext_followers:
                        try:
                            self.followers_cnt = hover_card.find_element(
                                "xpath",
                                './/a[contains(@href, "/verified_followers")]//span',
                            ).text

                            if self.followers_cnt == "":
                                self.followers_cnt = "0"

                            ext_followers = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return
                except NoSuchElementException:
                    if hover_attempt == 3:
                        self.error
                        return
                    hover_attempt += 1
                    sleep(0.5)
                    continue
                except StaleElementReferenceException:
                    self.error = True
                    return

            if ext_hover_card and ext_following and ext_followers:
                actions.reset_actions()

        self.tweet = (
            self.user,
            self.handle,
            self.date_time,
            self.verified,
            self.content,
            self.reply_cnt,
            self.retweet_cnt,
            self.like_cnt,
            self.analytics_cnt,
            self.tags,
            self.mentions,
            self.emojis,
            self.profile_img,
            self.tweet_link,
            self.tweet_id,
            self.user_id,
            self.following_cnt,
            self.followers_cnt,
            self.has_media,
        )

        pass
