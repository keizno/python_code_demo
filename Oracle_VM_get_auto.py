import oci
import time

# 1. 사용자 설정 (방금 찾으신 값들을 여기에 넣으세요)
config = {
    "user": "ocid1.user.oc1..aaa_이렇게 시작하는 코드를 붙여넣어 주세요...oqb7weqljvr4pfneiq",
    "key_file": "/home/ubuntu/oci-checker/oci_api_key-api키를 붙여넣어 주세요 확장자는 pem 입니다...", # 키 파일 경로
    "fingerprint": "ff:97:2a:79:77:5a:이렇게 생긴 핑거프린트를 붙여넣어 주세요...4d:82:a4:51",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaak4gn253vss5jhb_테난씨를 붙여넣어 주세요...s45ztgrc5q",
    "region": "ap-chuncheon-1"
}

# 2. 서버 상세 설정
AD = "VyXk:AP-CHUNCHEON-1-AD-1___춘천 리전의 AD를 붙여넣어 주세요.." # 사용자님의 고유 AD 이름
SUBNET_ID = "ocid1.subnet.oc1.ap-chuncheon-1.aaaaa_서브넷 아이디 필요..._nkpgprcgivnuh6pa"
IMAGE_ID = "ocid1.image.oc1.ap-chuncheon-1.aaaaaaaasonaqsoc5d4nd3wks6jh5jzqgiq2a3ewqlfrupyjoog2wvpzk6ta" # ARM용 우분투 입니다...이것으로 설치 가능
SSH_PUBLIC_KEY = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCr55n_이렇게 생긴 퍼블릭 키를 넣어주세요...@ssh용....LqwXqMJ"

compute_client = oci.core.ComputeClient(config)

def create_instance():
    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 서버 생성 시도 중...")
        print(f"이미지: {IMAGE_ID[:20]}... 서브넷: {SUBNET_ID[:20]}...")
        request = oci.core.models.LaunchInstanceDetails(
            display_name="My_ARM_Server",
            compartment_id=config['tenancy'],
            availability_domain=AD,
            shape="VM.Standard.A1.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=3, memory_in_gbs=20),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=IMAGE_ID, 
                boot_volume_size_in_gbs=150
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails( # 클래스명 수정 완료
                subnet_id=SUBNET_ID, 
                assign_public_ip=True
            ),
            metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY}
        )
        
        compute_client.launch_instance(request)
        print("🎉 축하합니다! 서버 생성 성공!")
        return True

    except oci.exceptions.ServiceError as e:
        if e.status == 500 or "Out of capacity" in str(e.message):
            print("❌ 현재 자리가 없습니다. (Out of capacity)")
        else:
            print(f"🚨 에러 발생: {e.message}")
        return False
    except Exception as e:
        print(f"❓ 예상치 못한 오류: {e}")
        return False

# 3. 무한 루프 실행 (이 부분이 반드시 있어야 합니다)
if __name__ == "__main__":
    while True:
        success = create_instance()
        if success:
            break  # 성공하면 무한 루프 종료
        
        print("😴 60초 대기 후 다시 시도합니다...")
        sys.stdout.flush()
        time.sleep(60) # 1분 대기