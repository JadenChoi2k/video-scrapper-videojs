from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.common import exceptions
from getpass import getpass
import requests
import os
import time

DEST_PATH = r'c:\src\inflearn'
page_url = 'https://www.inflearn.com/'
os_name_inhibit = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']


def clear_line():
    print(f'{" ":>100}', end='\r')


# 경로나 파일 명에서 쓸 수 없는 문자들을 삭제하기
def trim_path(name: str):
    for inhibit in os_name_inhibit:
        name = name.replace(inhibit, '')
    return name


def make_dest_path(dest):
    pass


class VideoCrawler:

    def __init__(self):
        self._driver = webdriver.Chrome()

    def login(self):
        login_id = input('아이디를 입력하세요 : ')
        pw = getpass('비밀번호를 입력하세요 : ')
        print('로그인 중입니다... 잠시만 기다려주세요', end='\r')

        self._driver.get(page_url)
        self._driver.find_elements(By.CLASS_NAME, "signin")[1].click()

        # id 입력
        id_input = self._driver.find_element(By.CLASS_NAME, 'form__input--email')
        id_input.send_keys(login_id)

        # pwd 입력
        pw_input = self._driver.find_element(By.CLASS_NAME, "e-sign-in-input")
        pw_input.send_keys(pw)

        time.sleep(1)
        # 로그인 버튼 클릭
        submit_btn = self._driver.find_element(By.CLASS_NAME, 'e-sign-in')
        submit_btn.click()

        clear_line()
        print('로그인되었습니다.')

        time.sleep(1)
        self._driver.get(page_url + 'my-courses')

    def get_video_from_current_page(self):
        return self.get_video_from_url(self._driver.current_url)

    def get_videos_from_current_lecture(self):
        return self.get_all_video_from_lecture(self._driver.current_url)

    # start, end는 시작과 끝 지점의 인덱스
    def get_all_video_from_lecture(self, url, start=0, end=4321):
        if self._driver.current_url != url:
            self._driver.get(url)

        try:
            unit_urls = [unit.get_attribute('href') for unit in
                         self._driver.find_elements('xpath', "//a[@class='unit_item']")]
        except exceptions.NoSuchElementException:
            print('강의 메인화면으로 이동해주셔야 다운로드가 가능합니다.')
            return None

        if start > end:
            raise ValueError('start value never greater than end')
        if end >= len(unit_urls):
            end = len(unit_urls) - 1
        size = end - start + 1

        for idx, unit_url in enumerate(unit_urls):
            if start > idx or idx > end:
                continue
            print(f'전체 강의 다운로드 {size} 중 {idx + 1}...')
            self.get_video_from_url(unit_url)

        print('강좌 다운로드가 모두 완료되었습니다.')

    def get_video_from_url(self, url):
        # requests 목록 초기화
        del self._driver.requests

        if self._driver.current_url != url:
            print('connecting to url...', url)
            self._driver.get(url)

        try:
            self._driver.find_element(By.TAG_NAME, 'video')
        except exceptions.NoSuchElementException:
            print('동영상이 없는 페이지입니다.')
            return None

        print('영상 대기 중...', end='\r')
        elapsed = 0
        while True:
            vid_js = self._driver.find_element(By.TAG_NAME, 'video-js')
            if 'vjs-playing' in vid_js.get_attribute('class'):
                break
            time.sleep(0.5)
            elapsed += 0.5
            if elapsed > 10:
                try:
                    self._driver.find_element(By.XPATH, "//button[contains(@class, 'vjs-paused')]").click()
                except Exception as e:
                    print(e)
            if elapsed > 30:
                print('대기 시간이 너무 오래 걸립니다...')
                return None
        print('영상 로드 완료', end='\r')
        # 만약 영상이 재생 중이라면 멈추게 하기.
        try:
            self._driver.find_element(By.XPATH, "//button[contains(@class, 'vjs-playing')]").click()
        except exceptions.NoSuchElementException:
            pass

        # 이거는 제외하고 받아오기
        title_except = ['목차', '커뮤니티 게시판', '노트']
        # ['현재 강의 제목', '전체 강의 제목', ...[목차 순서대로]]
        titles = [elem.text for elem in self._driver.find_elements(By.CLASS_NAME, 'title')
                  if elem.text not in title_except]
        # 코스 제목. titles 활용 시 안 나오는 오류가 있어서 선택자로 뽑기
        course_title = self._driver.find_element(By.CSS_SELECTOR, ".is-current .title").text
        course_index = titles[2:].index(course_title) + 1
        course_title = trim_path(course_title)
        course_filename = f'{course_index} - {course_title}.mp4'
        # 강의 제목
        lecture_title = titles[1]
        lecture_title = trim_path(lecture_title)
        print(f'[{lecture_title} - {course_title}] 강좌를 다운로드합니다.')
        # 파일이 이미 존재한다면 기본적으로 새로 생성하지 않는다.
        if os.path.isfile(os.path.join(DEST_PATH, lecture_title, course_filename)):
            print(os.path.join(DEST_PATH, lecture_title, course_filename))
            print('이미 존재하는 강의입니다. 다운로드하지 않습니다.')
            return None

        headers = {}
        root_url = None
        meta_info_url = None
        for request in self._driver.requests:
            if "https://vod.inflearn.com" in request.url and '.m3u8' in request.url:
                root_url = request.url[:request.url.rfind('/')] + '/'
                headers.update(request.headers)
                resp = requests.get(url=request.url, headers=headers)
                lines = [line for line in resp.text.strip().split('\n') if '#' not in line]
                meta_info_url = lines[-1]
                break
        if root_url is None:
            print('root url을 찾을 수 없습니다.')
            return None

        resp = requests.get(url=(root_url + meta_info_url), headers=headers)
        if resp.status_code != 200:
            print(resp.text)
            return None
        # get source url list
        sources = [src for src in resp.text.strip().split('\n') if '#' not in src]
        videos = []
        for idx, src in enumerate(sources):
            print(f'영상 다운로드 중... ({idx / len(sources) * 100:<4.1f}%)', end='\r')
            resp = requests.get(url=(root_url + src), headers=headers)
            if resp.status_code == 200:
                videos.append(resp.content)
        print('영상 다운로드 완료. 파일로 다운로드합니다.')

        # 다운로드 받을 장소.
        src_path = os.path.join(DEST_PATH, lecture_title)
        if not os.path.isdir(src_path):
            os.mkdir(src_path)
        with open(os.path.join(src_path, course_filename), 'wb') as f:
            for idx, vid in enumerate(videos):
                print(f'파일 합치는 중... ({idx / len(videos) * 100:<4.1f}%)', end='\r')
                f.write(vid)
            print('다운로드 완료.', lecture_title, '-', course_title)
            videos.clear()


if __name__ == '__main__':
    vc = VideoCrawler()
    vc.login()
    while True:
        userinput = input('현재 강의에서 모두 다운로드 받으려면 y 입력. 나가려면 out 입력. ')
        if userinput.lower() == 'y':
            vc.get_videos_from_current_lecture()
        elif userinput.lower() == 'out':
            break
